"""Coleta local de fotos reais: execute python tirar_foto.py."""
import base64
from datetime import datetime
import os
from pathlib import Path
import re
import subprocess
import sys
from threading import Event, Lock, Thread
import time
import tkinter as tk
from tkinter import messagebox, ttk
from uuid import uuid4

import cv2

from photo_duplicates import DuplicatePhotoError, guard_for

COLLECTION = Path(__file__).resolve().parent / "ai-service/datasets/local/coleta"
MAX_FRAME_AGE = 2.0


def session_directory(name, base=COLLECTION):
    name = name.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name):
        raise ValueError("Use até 64 letras sem acentos, números, _ ou - na sessão.")
    if name.split(".")[0].upper() in {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }:
        raise ValueError("Esse nome é reservado pelo Windows. Use sessao_001.")
    directory = (base / name).resolve()
    if not directory.is_relative_to(base.resolve()):
        raise ValueError("A pasta precisa estar dentro da pasta de coleta.")
    return directory


def save_photo(frame, directory, duplicate_root=None):
    ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not ok:
        raise RuntimeError("Não foi possível preparar a foto.")
    directory = Path(directory)
    root = Path(duplicate_root).resolve() if duplicate_root is not None else directory.resolve()
    if not directory.resolve().is_relative_to(root):
        raise ValueError('Destino fora da pasta de coleta.')
    guard_for(root).check(frame)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = directory / f"foto_{stamp}_{uuid4().hex[:8]}.jpg"
    # Python abre caminhos com acentos no Windows; xb impede sobrescritas.
    with path.open("xb") as output:
        output.write(encoded.tobytes())
    return path


class CameraReader:
    """Somente esta thread acessa o dispositivo; a janela nunca espera por read()."""

    def __init__(self, index, factory=None):
        self.index = index
        self.factory = factory or cv2.VideoCapture
        self.stop = Event()
        self.lock = Lock()
        self.frame = None
        self.timestamp = 0.0
        self.status = "Conectando à câmera..."
        self.thread = Thread(target=self.run, daemon=True)

    def start(self):
        self.thread.start()

    def snapshot(self):
        with self.lock:
            return self.frame, self.timestamp, self.status

    def fail(self, message):
        with self.lock:
            self.frame = None
            self.timestamp = 0.0
            self.status = message

    def run(self):
        camera = None
        try:
            camera = self.factory(self.index)
            if not camera.isOpened():
                self.fail("Câmera indisponível. Confira o índice, a conexão e outros aplicativos.")
                return
            while not self.stop.is_set():
                ok, frame = camera.read()
                if not ok or frame is None or frame.size == 0:
                    self.fail("Câmera desconectada ou sem imagem. Desconecte e tente novamente.")
                    return
                with self.lock:
                    self.frame = frame.copy()
                    self.timestamp = time.monotonic()
                    self.status = "Câmera conectada"
                self.stop.wait(0.01)
        except Exception as exc:
            self.fail(f"Falha na câmera: {exc}")
        finally:
            if camera is not None:
                camera.release()
            if self.stop.is_set():
                self.fail("Câmera desconectada.")


class PhotoApp:
    def __init__(self, root):
        self.root = root
        self.reader = None
        self.connected = False
        self.image = None
        self.rendered_at = 0.0
        self.saved = 0
        self.timer = None
        root.title("TecnoSolda | Coleta de fotos")
        root.geometry("1000x780")
        root.minsize(820, 700)
        root.protocol("WM_DELETE_WINDOW", self.close)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#f1f5f9")
        style.configure("TLabel", background="#f1f5f9", foreground="#0f172a", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10), padding=8)
        style.configure("Title.TLabel", font=("Segoe UI", 22, "bold"))
        style.configure("Capture.TButton", font=("Segoe UI", 12, "bold"), padding=12)

        page = ttk.Frame(root, padding=20)
        page.pack(fill="both", expand=True)
        ttk.Label(page, text="Coleta de fotos", style="Title.TLabel").pack(anchor="w")
        ttk.Label(page, text="Câmera real • Fotos manuais • Sem análise de IA").pack(anchor="w", pady=(4, 14))

        controls = ttk.Frame(page)
        controls.pack(fill="x")
        ttk.Label(controls, text="Câmera:").pack(side="left")
        self.camera_index = tk.StringVar(value="0")
        self.camera_input = ttk.Spinbox(controls, from_=0, to=20, width=4, textvariable=self.camera_index)
        self.camera_input.pack(side="left", padx=(6, 20))
        ttk.Label(controls, text="Sessão:").pack(side="left")
        self.session = tk.StringVar(value="sessao_001")
        ttk.Entry(controls, textvariable=self.session, width=25).pack(side="left", padx=6)
        self.connect_button = ttk.Button(controls, text="Conectar câmera", command=self.connect)
        self.connect_button.pack(side="right")
        self.disconnect_button = ttk.Button(controls, text="Desconectar", command=self.disconnect, state="disabled")
        self.disconnect_button.pack(side="right", padx=8)

        preview_box = tk.Frame(page, bg="#0f172a", height=400)
        preview_box.pack(fill="both", expand=True, pady=(16, 8))
        preview_box.pack_propagate(False)
        self.preview = tk.Label(preview_box, bg="#0f172a", fg="#cbd5e1",
                                text="Clique em Conectar câmera para ver a imagem.",
                                font=("Segoe UI", 12))
        self.preview.pack(fill="both", expand=True)
        self.status = tk.StringVar(value="Câmera desconectada.")
        ttk.Label(page, textvariable=self.status, wraplength=900).pack(anchor="w")

        actions = ttk.Frame(page)
        actions.pack(fill="x", pady=12)
        self.capture_button = ttk.Button(actions, text="Tirar foto", style="Capture.TButton",
                                         command=self.capture, state="disabled")
        self.capture_button.pack(side="left")
        ttk.Button(actions, text="Abrir pasta da sessão", command=self.open_folder).pack(side="left", padx=10)
        self.counter = tk.StringVar(value="0 fotos salvas nesta abertura")
        ttk.Label(actions, textvariable=self.counter).pack(side="right")

        self.destination = tk.StringVar()
        ttk.Label(page, textvariable=self.destination, wraplength=900).pack(anchor="w")
        self.last_photo = tk.StringVar(value="Nenhuma foto salva nesta abertura.")
        ttk.Label(page, textvariable=self.last_photo, wraplength=900).pack(anchor="w", pady=6)
        ttk.Label(page, text="Colete somente com autorização e sem soldagem ativa. "
                            "Feche outros aplicativos que estejam usando a câmera.",
                  wraplength=900).pack(anchor="w", pady=(6, 0))
        self.session.trace_add("write", self.update_destination)
        self.update_destination()
        self.tick()

    def update_destination(self, *_):
        try:
            self.destination.set(f"Destino: {session_directory(self.session.get())}")
        except ValueError as exc:
            self.destination.set(str(exc))

    def connect(self):
        if self.reader and self.reader.thread.is_alive():
            messagebox.showinfo("Câmera", "Aguarde a câmera anterior encerrar. Se o driver travou, feche e reabra o programa.")
            return
        try:
            index = int(self.camera_index.get())
            if index < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Câmera", "Informe um índice inteiro a partir de 0.")
            return
        self.reader = CameraReader(index)
        self.connected = True
        self.rendered_at = 0.0
        self.camera_input.configure(state="disabled")
        self.connect_button.configure(state="disabled")
        self.disconnect_button.configure(state="normal")
        self.reader.start()

    def disconnect(self):
        self.connected = False
        if self.reader:
            self.reader.stop.set()
        self.camera_input.configure(state="normal")
        self.connect_button.configure(state="normal")
        self.disconnect_button.configure(state="disabled")
        self.capture_button.configure(state="disabled")
        self.clear_preview("Câmera desconectada.")
        self.status.set("Câmera desconectada.")

    def clear_preview(self, text):
        self.preview.configure(image="", text=text)
        self.image = None
        self.rendered_at = 0.0

    def fresh_frame(self):
        if not self.connected or not self.reader or self.reader.stop.is_set():
            return None
        frame, timestamp, _ = self.reader.snapshot()
        if frame is None or time.monotonic() - timestamp > MAX_FRAME_AGE:
            return None
        return frame

    def tick(self):
        try:
            if self.connected and self.reader:
                frame, timestamp, status = self.reader.snapshot()
                fresh = frame is not None and time.monotonic() - timestamp <= MAX_FRAME_AGE
                if fresh:
                    if timestamp != self.rendered_at:
                        height, width = frame.shape[:2]
                        scale = min(900 / width, 420 / height, 1.0)
                        small = cv2.resize(frame, (max(1, int(width * scale)), max(1, int(height * scale))),
                                           interpolation=cv2.INTER_AREA)
                        ok, encoded = cv2.imencode(".png", small)
                        if not ok:
                            raise RuntimeError("Não foi possível exibir a prévia.")
                        self.image = tk.PhotoImage(master=self.root, data=base64.b64encode(encoded.tobytes()))
                        self.preview.configure(image=self.image, text="")
                        self.rendered_at = timestamp
                    self.status.set(f"Câmera conectada • Foto original: {frame.shape[1]} × {frame.shape[0]} pixels")
                    self.capture_button.configure(state="normal")
                else:
                    if frame is not None:
                        status = "Sem quadros recentes. Desconecte e reconecte a câmera."
                    self.status.set(status)
                    self.clear_preview(status)
                    self.capture_button.configure(state="disabled")
                    if not self.reader.thread.is_alive():
                        self.connect_button.configure(state="normal")
                        self.camera_input.configure(state="normal")
        except (cv2.error, tk.TclError, RuntimeError) as exc:
            self.disconnect()
            self.status.set(f"Falha na prévia: {exc}")
        self.timer = self.root.after(66, self.tick)

    def capture(self):
        frame = self.fresh_frame()
        if frame is None:
            self.capture_button.configure(state="disabled")
            self.status.set("Sem imagem recente. Reconecte a câmera antes de fotografar.")
            return
        try:
            path = save_photo(frame, session_directory(self.session.get()), duplicate_root=COLLECTION)
        except DuplicatePhotoError as exc:
            self.last_photo.set(str(exc))
            messagebox.showwarning('Foto muito parecida', str(exc))
            return
        except (OSError, ValueError, RuntimeError, cv2.error) as exc:
            messagebox.showerror("Não foi possível salvar", str(exc))
            return
        self.saved += 1
        self.counter.set(f"{self.saved} fotos salvas nesta abertura")
        self.last_photo.set(f"Última foto: {path.parent.name}/{path.name}")

    def open_folder(self):
        try:
            folder = session_directory(self.session.get())
            folder.mkdir(parents=True, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(str(folder))
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(folder)])
        except (OSError, ValueError) as exc:
            messagebox.showerror("Pasta da sessão", str(exc))

    def close(self):
        if self.reader:
            self.reader.stop.set()
        if self.timer is not None:
            self.root.after_cancel(self.timer)
        self.root.destroy()


def main():
    root = tk.Tk()
    PhotoApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

