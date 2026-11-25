"""AIRSTRINGS — draw and pluck gesture-controlled musical strings (v2.3).

Requires Python 3.11, MediaPipe Tasks, OpenCV, NumPy and Pygame.
DRAW: pinch thumb + index; move while pinched; release to leave a real string.
PLAY: swipe an index or middle fingertip through the created string.
LIVE: press T; show two hands to stretch a live string between index fingertips.
    Pluck with middle fingertips crossing the string, or make a quick pinch on
    either hand to sound the live string.
C chord/note, U undo, X clear, L tuning, T live/draw, V switch camera, Q quit.
"""
from __future__ import annotations

import math
import random
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
import pygame

# ------------------------------- SETTINGS -------------------------------
CAMERA_INDEX = 0  # fallback if no saved camera choice
CAMERA_CHOICES = (0, 1, 2)  # camera indices previously confirmed available on this Mac
CAMERA_CONFIG = Path(__file__).resolve().parent / "camera_index.txt"
FRAME_WIDTH, FRAME_HEIGHT = 960, 540
WINDOW_NAME = "AIRSTRINGS | Draw + Play"
SAMPLE_RATE = 44100
SOUND_DURATION = 1.20
PLUCK_COOLDOWN = 0.19
MIN_STROKE_PX = 9
MAX_STROKE_PX = 150  # prevents a tracking jump causing accidental plucks
MIN_STRING_LENGTH_PX = 65
MAX_STRINGS = 12
PINCH_START_RATIO = 0.38   # thumb/index distance divided by palm width
PINCH_END_RATIO = 0.64     # hysteresis to avoid flickering
PINCH_CONFIRM_FRAMES = 2
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
MODEL_PATH = Path(__file__).resolve().parent / "hand_landmarker.task"

# White-key C major. Longer strings -> lower notes; shorter -> higher notes.
SCALE_MIDI = (60, 62, 64, 65, 67, 69, 71, 72, 74, 76, 77, 79)
NOTE_LABELS = ("C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5")
CHORD_LABELS = ("C", "Dm", "Em", "F", "G", "Am", "Bdim", "C")
FINGER_TIPS = (8, 12)
HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20), (0, 17),
)

Point = tuple[int, int]


@dataclass
class AirString:
    identifier: int
    start: Point
    end: Point
    degree: int
    made_at: float
    last_hit: float = -100.0
    hit_at: Point | None = None


@dataclass
class HandState:
    pinching: bool = False
    candidate_frames: int = 0
    candidate_start: Point | None = None
    start: Point | None = None
    end: Point | None = None
    pluck_block_until: float = 0.0
    previous_tips: dict[int, Point] | None = None
    last_seen: float = 0.0

    def __post_init__(self) -> None:
        if self.previous_tips is None:
            self.previous_tips = {}


@dataclass
class Spark:
    x: float
    y: float
    vx: float
    vy: float
    born: float
    ttl: float
    colour: tuple[int, int, int]


def length(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def length_to_degree(pixel_length: float, diagonal: float) -> int:
    """Longer = lower; clamp playable lengths into the C4–C5 diatonic scale."""
    hi = max(230.0, diagonal * 0.72)
    fraction = (hi - pixel_length) / (hi - MIN_STRING_LENGTH_PX)
    return min(7, max(0, int(round(fraction * 7))))


def segment_crossing(p: Point, q: Point, a: Point, b: Point) -> Point | None:
    """Return intersection of finger motion p->q and string a->b, any angle.

    Reject near-endpoint hits (anchor touches) and parallel/collinear moves.
    """
    rx, ry = q[0] - p[0], q[1] - p[1]
    sx, sy = b[0] - a[0], b[1] - a[1]
    denom = rx * sy - ry * sx
    if abs(denom) < 1e-6:
        return None
    ax, ay = a[0] - p[0], a[1] - p[1]
    t = (ax * sy - ay * sx) / denom
    u = (ax * ry - ay * rx) / denom
    if 0.0 <= t <= 1.0 and 0.045 <= u <= 0.955:
        return (round(p[0] + t * rx), round(p[1] + t * ry))
    return None


def midi_to_hz(midi: int) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12.0)


def synthesise(notes: tuple[int, ...]) -> np.ndarray:
    """Harp-like plucked-note PCM; synthesized locally, no copyrighted samples."""
    t = np.arange(int(SAMPLE_RATE * SOUND_DURATION), dtype=np.float64) / SAMPLE_RATE
    wave = np.zeros_like(t)
    for midi in notes:
        freq = midi_to_hz(midi)
        phase = 2 * math.pi * freq * (t + 0.0001 * np.sin(2 * math.pi * 4.4 * t))
        wave += (0.77 * np.sin(phase)
                 + 0.22 * np.sin(2 * phase)
                 + 0.11 * np.sin(3 * phase))
    env = np.clip(t / 0.006, 0.0, 1.0) * np.exp(-3.15 * t)
    wave = np.clip(wave * env * (0.45 / max(1.0, len(notes) * 0.82)), -0.95, 0.95)
    pcm = (wave * 32767).astype(np.int16)
    return np.ascontiguousarray(np.column_stack((pcm, pcm)))


def create_sounds() -> tuple[list[pygame.mixer.Sound], list[pygame.mixer.Sound]]:
    single, chords = [], []
    for degree in range(8):
        single.append(pygame.sndarray.make_sound(synthesise((SCALE_MIDI[degree],))))
        # Use two-octave scale for a complete final C5 chord.
        chord_notes = tuple(SCALE_MIDI[degree + i] for i in (0, 2, 4))
        chords.append(pygame.sndarray.make_sound(synthesise(chord_notes)))
    return single, chords


def download_model_if_needed() -> None:
    if MODEL_PATH.exists() and MODEL_PATH.stat().st_size > 100_000:
        return
    print("Downloading MediaPipe hand model (once only)...")
    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    except Exception as exc:
        MODEL_PATH.unlink(missing_ok=True)
        raise RuntimeError(
            "Cannot download model. Open this URL in your browser:\n"
            f"{MODEL_URL}\nSave it as hand_landmarker.task in {MODEL_PATH.parent}"
        ) from exc


def load_camera_index() -> int:
    """Use the last camera chosen in the app, or the original default."""
    try:
        candidate = int(CAMERA_CONFIG.read_text(encoding="utf-8").strip())
        if candidate in CAMERA_CHOICES:
            return candidate
    except (OSError, ValueError):
        pass
    return CAMERA_INDEX


def save_camera_index(index: int) -> None:
    try:
        CAMERA_CONFIG.write_text(f"{index}\n", encoding="utf-8")
    except OSError as exc:
        print(f"Could not save camera selection: {exc}")


def switch_camera(capture: cv2.VideoCapture, current: int,
                  desired: int) -> tuple[cv2.VideoCapture, int, bool]:
    """Switch camera without leaving the previous device open.

    Failed switches reopen the previous device so the user can keep playing.
    """
    if desired == current:
        return capture, current, False
    capture.release()
    try:
        new_capture = open_camera(desired)
    except RuntimeError as exc:
        print(f"Camera {desired} not available: {exc}")
        print(f"Returning to camera {current}.")
        return open_camera(current), current, False
    save_camera_index(desired)
    print(f"Now using camera {desired}. Press V to change camera again.")
    return new_capture, desired, True


def open_camera(camera_index: int) -> cv2.VideoCapture:
    # Your macOS camera 0 test succeeded specifically via AVFoundation.
    if sys.platform == "darwin":
        backends = (cv2.CAP_AVFOUNDATION, cv2.CAP_ANY)
    elif sys.platform.startswith("win"):
        backends = (cv2.CAP_DSHOW, cv2.CAP_ANY)
    else:
        backends = (cv2.CAP_ANY,)
    for backend in backends:
        capture = cv2.VideoCapture(camera_index, backend)
        if capture.isOpened():
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
            for _ in range(5):
                ok, img = capture.read()
                if ok and img is not None:
                    return capture
                time.sleep(0.06)
        capture.release()
    raise RuntimeError(
        f"Cannot read camera {camera_index}. Check camera privacy permission, "
        "close camera-using apps, and try again."
    )


def get_points(landmarks: list, width: int, height: int) -> list[Point]:
    return [
        (int(np.clip(p.x, 0, 1) * (width - 1)),
         int(np.clip(p.y, 0, 1) * (height - 1)))
        for p in landmarks
    ]


def draw_hand(frame: np.ndarray, points: list[Point], colour: tuple[int, int, int]) -> None:
    for a, b in HAND_CONNECTIONS:
        cv2.line(frame, points[a], points[b], (70, 210, 95), 1, cv2.LINE_AA)
    for idx, pt in enumerate(points):
        if idx in (4, 8):
            cv2.circle(frame, pt, 6, colour, -1, cv2.LINE_AA)
        elif idx == 12:
            cv2.circle(frame, pt, 5, (255, 220, 110), -1, cv2.LINE_AA)
        else:
            cv2.circle(frame, pt, 2, (120, 245, 135), -1, cv2.LINE_AA)


def add_sparks(sparks: list[Spark], at: Point, now: float, count: int = 14) -> None:
    for _ in range(count):
        angle = random.random() * 2 * math.pi
        speed = random.uniform(55, 265)
        sparks.append(Spark(float(at[0]), float(at[1]), math.cos(angle) * speed,
                            math.sin(angle) * speed, now, random.uniform(0.18, 0.54),
                            random.choice(((255, 210, 255), (235, 120, 255),
                                           (255, 255, 200), (250, 210, 150)))))
    # Bounded particle system, even during long recording sessions.
    del sparks[:-320]


def string_curve(string: AirString, now: float) -> list[Point]:
    a, b = string.start, string.end
    age = now - string.last_hit
    if age < 0 or age > 0.8:
        return [a, b]
    vibration = 19 * math.exp(-5.6 * age)
    dx, dy = b[0] - a[0], b[1] - a[1]
    full = max(1.0, math.hypot(dx, dy))
    perp_x, perp_y = -dy / full, dx / full
    out: list[Point] = []
    for k in range(31):
        u = k / 30.0
        offset = vibration * math.sin(math.pi * u) * math.sin(2 * math.pi * (2.7 * u - 8.5 * age))
        out.append((int(a[0] + u * dx + perp_x * offset),
                    int(a[1] + u * dy + perp_y * offset)))
    return out


def draw_string_glow(frame: np.ndarray, strings: list[AirString],
                     preview: list[tuple[Point, Point]], now: float,
                     chords: bool, show_labels: bool = True) -> None:
    glow = np.zeros_like(frame)
    for s in strings:
        curve = np.array(string_curve(s, now), dtype=np.int32).reshape((-1, 1, 2))
        hot = now - s.last_hit < 0.34
        cv2.polylines(glow, [curve], False, (225, 80, 250) if hot else (225, 75, 170),
                      13 if hot else 8, cv2.LINE_AA)
    for a, b in preview:
        cv2.line(glow, a, b, (255, 165, 215), 10, cv2.LINE_AA)
    glow = cv2.GaussianBlur(glow, (0, 0), sigmaX=7)
    cv2.addWeighted(frame, 1.0, glow, 0.64, 0, dst=frame)

    height, width = frame.shape[:2]
    for s in strings:
        age = now - s.last_hit
        hot = age < 0.34
        curve = np.array(string_curve(s, now), dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(frame, [curve], False, (255, 245, 255) if hot else (255, 155, 235),
                      3 if hot else 2, cv2.LINE_AA)
        for anchor in (s.start, s.end):
            cv2.circle(frame, anchor, 4, (255, 225, 255), -1, cv2.LINE_AA)
        if show_labels:
            middle = ((s.start[0] + s.end[0]) // 2, (s.start[1] + s.end[1]) // 2)
            name = CHORD_LABELS[s.degree] if chords else NOTE_LABELS[s.degree]
            label_pos = (min(width - 40, middle[0] + 10), max(75, min(height - 25, middle[1] - 10)))
            cv2.putText(frame, name, label_pos,
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (245, 225, 255), 2, cv2.LINE_AA)
        if hot and s.hit_at is not None:
            radius = int(5 + max(0, age) * 100)
            cv2.circle(frame, s.hit_at, radius, (250, 200, 255), 2, cv2.LINE_AA)

    for a, b in preview:
        cv2.line(frame, a, b, (255, 240, 255), 2, cv2.LINE_AA)
        cv2.circle(frame, a, 7, (255, 245, 255), 2, cv2.LINE_AA)
        cv2.circle(frame, b, 8, (255, 220, 210), -1, cv2.LINE_AA)


def render_sparks(frame: np.ndarray, sparks: list[Spark], now: float) -> None:
    keep = []
    for s in sparks:
        age = now - s.born
        if 0 <= age < s.ttl:
            t = age / s.ttl
            x = int(s.x + s.vx * age)
            y = int(s.y + s.vy * age + 120 * age * age)
            radius = 2 if t < 0.6 else 1
            cv2.circle(frame, (x, y), radius, s.colour, -1, cv2.LINE_AA)
            keep.append(s)
    sparks[:] = keep


def hud(frame: np.ndarray, live: bool, chords: bool, by_length: bool,
        count: int, status: str, camera_index: int) -> None:
    h, w = frame.shape[:2]
    shade = frame.copy()
    cv2.rectangle(shade, (0, 0), (w, 97), (13, 10, 24), -1)
    cv2.rectangle(shade, (0, h - 43), (w, h), (13, 10, 24), -1)
    cv2.addWeighted(shade, 0.83, frame, 0.17, 0, dst=frame)
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(frame, "AIRSTRINGS  |  BUILD YOUR OWN INSTRUMENT", (16, 29), font,
                0.7, (255, 225, 255), 2, cv2.LINE_AA)
    style = "LIVE: between index fingers" if live else "DRAW: pinch, drag, release"
    tune = "Length tunes pitch" if by_length else "Creation-order scale"
    cv2.putText(frame, f"{style}   |   {'CHORDS' if chords else 'NOTES'}   |   {tune}",
                (17, 55), font, 0.51, (165, 245, 220), 1, cv2.LINE_AA)
    cv2.putText(frame, "T: live/draw  C: chords  L: tuning  V: camera  U: undo  X: clear  Q: quit",
                (17, 80), font, 0.48, (190, 185, 250), 1, cv2.LINE_AA)
    cv2.putText(frame, f"CAM {camera_index}", (w - 115, 29), font,
                0.55, (255, 230, 130), 2, cv2.LINE_AA)
    cv2.putText(frame, f"{count} saved strings", (17, h - 16), font,
                0.52, (255, 235, 255), 1, cv2.LINE_AA)
    if status:
        (tw, _), _ = cv2.getTextSize(status, font, 0.50, 1)
        cv2.putText(frame, status, (max(12, w - tw - 16), h - 16), font,
                    0.50, (145, 245, 255), 1, cv2.LINE_AA)


def pluck(s: AirString, at: Point, now: float, notes: list, chords: list,
          use_chords: bool, sparks: list[Spark]) -> None:
    s.last_hit = now
    s.hit_at = at
    sounds = chords if use_chords else notes
    sounds[s.degree].play()
    add_sparks(sparks, at, now)


def main() -> None:
    print("AIRSTRINGS v2.3 — draw strings by pinching thumb + index, moving, releasing.")
    print("Use a second hand or release the pinch to pluck by sweeping across a string.")
    print("T: live tether, C: chords, L: tuning, V: switch camera, U: undo, X: clear, Q: quit")
    download_model_if_needed()
    pygame.mixer.pre_init(SAMPLE_RATE, -16, 2, 256)
    pygame.init()
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.set_num_channels(32)
    except pygame.error as exc:
        raise RuntimeError("Audio could not start. Check Mac output/speakers.") from exc

    notes, chords = create_sounds()
    camera_index = load_camera_index()
    print(f"Opening camera {camera_index} (press V while the video window is selected to change it).")
    capture = open_camera(camera_index)
    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(MODEL_PATH)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    strings: list[AirString] = []
    sparks: list[Spark] = []
    hands: dict[str, HandState] = {}
    last_hits: dict[tuple[str, int, int], float] = {}
    chords_on = False
    live_mode = False
    by_length = True
    next_identifier = 1
    previous_live_length = 0.0
    live_last_hit = -100.0
    live_last_point: Point | None = None
    last_live_pinch: dict[str, float] = {}
    start_ns = time.monotonic_ns()
    last_timestamp_ms = -1

    try:
        with mp.tasks.vision.HandLandmarker.create_from_options(options) as landmarker:
            while True:
                ok, frame = capture.read()
                if not ok:
                    print("The webcam stopped returning frames.")
                    break
                frame = cv2.flip(frame, 1)
                frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))
                h, w = frame.shape[:2]
                rgb = np.ascontiguousarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                ts_ms = max(last_timestamp_ms + 1, (time.monotonic_ns() - start_ns) // 1_000_000)
                last_timestamp_ms = ts_ms
                result = landmarker.detect_for_video(image, ts_ms)
                now = time.monotonic()
                # Display the webcam exactly as the camera provides it.
                # No dimming, software brightness, or exposure overrides.
                visible_hands: dict[str, list[Point]] = {}
                for i, lm in enumerate(result.hand_landmarks):
                    side = result.handedness[i][0].category_name if result.handedness else f"Hand{i}"
                    # If both predictions have same side, avoid silently dropping one.
                    if side in visible_hands:
                        side = f"{side}{i}"
                    visible_hands[side] = get_points(lm, w, h)

                previews: list[tuple[Point, Point]] = []
                status = ""
                if live_mode:
                    # The live, elastic string is generated between two index tips.
                    # The midpoint follows hands as their separation changes.
                    live_string: AirString | None = None
                    if len(visible_hands) >= 2:
                        sides = list(visible_hands)[:2]
                        a = visible_hands[sides[0]][8]
                        b = visible_hands[sides[1]][8]
                        distance = length(a, b)
                        if distance >= MIN_STRING_LENGTH_PX:
                            degree = length_to_degree(distance, math.hypot(w, h)) if by_length else 0
                            live_string = AirString(0, a, b, degree, now, live_last_hit, live_last_point)
                            previous_live_length = distance
                            status = "Move hands apart to tune the live string"
                        else:
                            status = "Separate index fingertips to make a string"
                    else:
                        status = "Show BOTH hands to create a live string"
                    live_strings = [live_string] if live_string else []
                    for side, points in visible_hands.items():
                        state = hands.setdefault(side, HandState())
                        state.last_seen = now
                        for tip in (12,):  # Index anchors the line; middle plucks it.
                            cur = points[tip]
                            prev = state.previous_tips.get(tip)
                            if live_string and prev and MIN_STROKE_PX <= length(prev, cur) <= MAX_STROKE_PX:
                                hit = segment_crossing(prev, cur, live_string.start, live_string.end)
                                key = (side, tip, 0)
                                if hit and now - last_hits.get(key, -100) > PLUCK_COOLDOWN:
                                    pluck(live_string, hit, now, notes, chords, chords_on, sparks)
                                    live_last_hit, live_last_point = now, hit
                                    last_hits[key] = now
                            state.previous_tips[tip] = cur
                        # Quick pinch gesture gives another way to play with both hands
                        # occupied as string anchors.
                        palm = max(24.0, length(points[5], points[17]))
                        gap = length(points[4], points[8]) / palm
                        if gap < PINCH_START_RATIO and not state.pinching:
                            state.pinching = True
                            if live_string and now - last_live_pinch.get(side, -100) > PLUCK_COOLDOWN:
                                hit = ((live_string.start[0] + live_string.end[0]) // 2,
                                       (live_string.start[1] + live_string.end[1]) // 2)
                                pluck(live_string, hit, now, notes, chords, chords_on, sparks)
                                live_last_hit, live_last_point = now, hit
                                last_live_pinch[side] = now
                        elif gap > PINCH_END_RATIO:
                            state.pinching = False
                    draw_string_glow(frame, live_strings, [], now, chords_on)
                else:
                    for side, points in visible_hands.items():
                        state = hands.setdefault(side, HandState())
                        state.last_seen = now
                        palm = max(24.0, length(points[5], points[17]))
                        pinch_ratio = length(points[4], points[8]) / palm
                        cursor = ((points[4][0] + points[8][0]) // 2,
                                  (points[4][1] + points[8][1]) // 2)
                        if not state.pinching:
                            if pinch_ratio < PINCH_START_RATIO:
                                if state.candidate_frames == 0:
                                    state.candidate_start = cursor
                                state.candidate_frames += 1
                                if state.candidate_frames >= PINCH_CONFIRM_FRAMES:
                                    state.pinching = True
                                    state.start = state.candidate_start
                                    state.end = cursor
                                    state.previous_tips.clear()
                            else:
                                state.candidate_frames = 0
                                state.candidate_start = None
                        else:
                            if pinch_ratio <= PINCH_END_RATIO:
                                state.end = cursor
                            else:
                                # Commit the drawn line: last still-pinched cursor is
                                # used, not the release frame's spread fingertips.
                                if (state.start is not None and state.end is not None
                                        and length(state.start, state.end) >= MIN_STRING_LENGTH_PX):
                                    distance = length(state.start, state.end)
                                    degree = (length_to_degree(distance, math.hypot(w, h))
                                              if by_length else len(strings) % 8)
                                    strings.append(AirString(next_identifier, state.start,
                                                             state.end, degree, now))
                                    next_identifier += 1
                                    if len(strings) > MAX_STRINGS:
                                        strings.pop(0)
                                    add_sparks(sparks, state.start, now, 9)
                                    add_sparks(sparks, state.end, now, 9)
                                    status = "String created! Swipe across it to play"
                                    print(f"Saved string #{next_identifier - 1}: {NOTE_LABELS[degree]} "
                                          f"({int(distance)} px)")
                                else:
                                    status = "Draw a longer string (at least 65 pixels)"
                                state.pinching = False
                                state.candidate_frames = 0
                                state.start = None
                                state.end = None
                                state.previous_tips.clear()
                                state.pluck_block_until = now + 0.25
                        if state.pinching and state.start and state.end:
                            previews.append((state.start, state.end))
                            status = "Drawing... move pinched fingers; release to save"
                        elif not state.pinching and now >= state.pluck_block_until:
                            for tip in FINGER_TIPS:
                                cur = points[tip]
                                prev = state.previous_tips.get(tip)
                                if prev and MIN_STROKE_PX <= length(prev, cur) <= MAX_STROKE_PX:
                                    for s in strings:
                                        hit = segment_crossing(prev, cur, s.start, s.end)
                                        key = (side, tip, s.identifier)
                                        if hit and now - last_hits.get(key, -100) >= PLUCK_COOLDOWN:
                                            pluck(s, hit, now, notes, chords, chords_on, sparks)
                                            last_hits[key] = now
                                state.previous_tips[tip] = cur
                    draw_string_glow(frame, strings, previews, now, chords_on)
                    if not visible_hands:
                        status = "Show a hand; pinch thumb + index and draw a line"
                    elif not status and not strings:
                        status = "Pinch + drag + release to create your first string"
                    elif not status:
                        status = "Swipe a finger THROUGH your lines to play"

                for side, points in visible_hands.items():
                    draw_hand(frame, points, (100, 225, 255))
                    if not live_mode and hands[side].pinching:
                        p = ((points[4][0] + points[8][0]) // 2,
                             (points[4][1] + points[8][1]) // 2)
                        cv2.circle(frame, p, 13, (245, 255, 255), 2, cv2.LINE_AA)

                render_sparks(frame, sparks, now)
                hud(frame, live_mode, chords_on, by_length, len(strings), status, camera_index)
                cv2.imshow(WINDOW_NAME, frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord('q'), 27):
                    break
                if key == ord('v'):
                    # Device 0 can be an iPhone via Continuity Camera. Use this
                    # shortcut to choose the actual Mac webcam by looking at the
                    # image. The chosen index is remembered for future launches.
                    index_pos = CAMERA_CHOICES.index(camera_index)
                    candidates = (CAMERA_CHOICES[(index_pos + offset) % len(CAMERA_CHOICES)]
                                  for offset in range(1, len(CAMERA_CHOICES)))
                    for desired in candidates:
                        capture, updated_index, changed = switch_camera(
                            capture, camera_index, desired)
                        camera_index = updated_index
                        if changed:
                            # String positions belonged to the previous camera
                            # coordinate system; clear to prevent accidental plucks.
                            strings.clear()
                            sparks.clear()
                            hands.clear()
                            last_hits.clear()
                            live_last_hit = -100.0
                            print("Switched camera. Draw new strings on this camera view.")
                            break
                elif key == ord('c'):
                    chords_on = not chords_on
                elif key == ord('t'):
                    live_mode = not live_mode
                    hands.clear()
                    last_hits.clear()
                    live_last_hit = -100.0
                elif key == ord('l'):
                    by_length = not by_length
                    for i, s in enumerate(strings):
                        s.degree = (length_to_degree(length(s.start, s.end), math.hypot(w, h))
                                    if by_length else i % 8)
                elif key == ord('u'):
                    if strings:
                        strings.pop()
                elif key == ord('x'):
                    strings.clear()
                # Discard stale hand paths; otherwise they could reconnect across
                # frames and falsely pluck a string when the hand returns.
                for side in list(hands):
                    if side not in visible_hands:
                        hands[side].previous_tips.clear()
                        if hands[side].pinching:
                            hands[side].pinching = False
                            hands[side].start = None
                            hands[side].end = None
                        hands[side].candidate_frames = 0
                    if now - hands[side].last_seen > 1.0:
                        del hands[side]
    finally:
        capture.release()
        cv2.destroyAllWindows()
        pygame.mixer.quit()
        pygame.quit()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nERROR: {exc}")
        raise