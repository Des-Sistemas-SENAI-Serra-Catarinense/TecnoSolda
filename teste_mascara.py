"""Abra com python teste_mascara.py. Mostra se a máscara está levantada ou abaixada.
Ensaio visual local, sem treino e sem sinalização física."""
import base64
from threading import Event, Lock, Thread
import time
import tkinter as tk
from tkinter import ttk

import cv2

from helmet_experiment import FRESH_SECONDS, Prediction, SignalGate
from mask_state import FaceMaskDetector
from tirar_foto import CameraReader


class AnalysisWorker:
    def __init__(self, detector, crop=lambda frame: frame):
        self.detector = detector
        self.crop = crop
        self.stop = Event()
        self.lock = Lock()
        self.revision = 0
        self.reader = None
        self.result = None
        self.thread = Thread(target=self.run, daemon=True)
        self.thread.start()

    def configure(self, reader=None):
        with self.lock:
            self.revision += 1
            self.reader = reader
            self.result = None

    def snapshot(self):
        with self.lock:
            return self.result

    def run(self):
        previous = None
        while not self.stop.wait(0.08):
            with self.lock:
                revision, reader = self.revision, self.reader
            if reader is None or reader.stop.is_set():
                continue
            frame, captured_at, _ = reader.snapshot()
            if frame is None or time.monotonic() - captured_at > FRESH_SECONDS:
                with self.lock:
                    if revision == self.revision:
                        self.result = None
                continue
            key = (revision, captured_at)
            if key == previous:
                continue
            previous = key
            started = time.monotonic()
            try:
                prediction = self.detector.predict(self.crop(frame))
            except Exception as exc:
                prediction = Prediction("inconclusiva", 0.0, 0.0, f"Falha de análise: {exc}")
            duration = (time.monotonic() - started) * 1000
            with self.lock:
                if revision == self.revision:
                    self.result = (captured_at, prediction, duration)

    def close(self):
        self.configure()
        self.stop.set()


class HelmetTestApp:
    def __init__(self, root):
        self.root = root
        self.reader = None
        self.connected = False
        self.running = False
        self.photo = None
        self.rendered = 0.0
        self.timer = None
        self.gate = SignalGate()
        self.worker = AnalysisWorker(FaceMaskDetector())
        root.title("TecnoSolda | Teste da máscara de soldagem")
        root.geometry("760x780")
        root.minsize(700, 720)
        root.protocol("WM_DELETE_WINDOW", self.close)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#eef2f6")
        style.configure("TLabel", background="#eef2f6", foreground="#14253b", font=("Segoe UI", 10))
        style.configure("TButton", padding=7, font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 21, "bold"))
        page = ttk.Frame(root, padding=18)
        page.pack(fill="both", expand=True)
        ttk.Label(page, text="Teste da máscara de soldagem", style="Title.TLabel").pack(anchor="w")
        ttk.Label(page, text="Máscara levantada ou abaixada • Sem treino • Sem acionamento físico").pack(anchor="w", pady=(3, 12))
        top = ttk.Frame(page)
        top.pack(fill="x")
        ttk.Label(top, text="Câmera").pack(side="left")
        self.index = tk.StringVar(value="0")
        self.index_input = ttk.Spinbox(top, from_=0, to=20, width=4, textvariable=self.index)
        self.index_input.pack(side="left", padx=8)
        self.connect_button = ttk.Button(top, text="Conectar", command=self.connect)
        self.connect_button.pack(side="left")
        self.disconnect_button = ttk.Button(top, text="Desconectar", command=self.disconnect, state="disabled")
        self.disconnect_button.pack(side="left", padx=8)
        self.test_button = ttk.Button(top, text="Iniciar teste", command=self.toggle_test, state="disabled")
        self.test_button.pack(side="right")

        view = tk.Frame(page, bg="#101b2c", height=300)
        view.pack(fill="both", expand=True, pady=14)
        view.pack_propagate(False)
        self.preview = tk.Label(view, bg="#101b2c", fg="#d8e1ee", font=("Segoe UI", 12),
                                text="Conecte a câmera para começar.")
        self.preview.pack(fill="both", expand=True)
        ttk.Label(page, text="Analisa a imagem inteira da câmera. Mantenha a cabeça visível, de frente para ela.",
                  wraplength=700).pack(anchor="w")
        self.camera_status = tk.StringVar(value="Câmera desconectada")
        ttk.Label(page, textvariable=self.camera_status, wraplength=700).pack(anchor="w", pady=(4, 0))
        self.signal = tk.Label(page, text="INCONCLUSIVO • Teste parado", bg="#fef3c7", fg="#92400e",
                               font=("Segoe UI", 17, "bold"), padx=10, pady=16, wraplength=660)
        self.signal.pack(fill="x", pady=(12, 6))
        self.inference_info = tk.StringVar(value="Conecte a câmera e inicie o teste.")
        ttk.Label(page, textvariable=self.inference_info, wraplength=700).pack(anchor="w")
        ttk.Label(page, text="Vermelho: máscara levantada (rosto visível)\n"
                             "Verde: máscara abaixada (rosto coberto), após 0,5 s estável\n"
                             "Amarelo: teste parado ou imagem indisponível\n"
                             "O verde é apenas indicação neste ensaio; não libera soldagem.",
                  wraplength=700).pack(anchor="w", pady=(10, 0))

    def set_signal(self, color, detail=""):
        titles = {"red": "VERMELHO • Máscara levantada",
                  "green": "VERDE • Máscara abaixada",
                  "amber": "INCONCLUSIVO"}
        colors = {"red": ("#fee2e2", "#991b1b"), "green": ("#dcfce7", "#166534"),
                  "amber": ("#fef3c7", "#92400e")}
        bg, fg = colors[color]
        text = titles[color] + (f" • {detail}" if detail else "")
        self.signal.configure(text=text, bg=bg, fg=fg)

    def stop_test(self):
        self.running = False
        self.worker.configure()
        self.gate.reset()
        self.test_button.configure(text="Iniciar teste")
        self.set_signal("amber", "Teste parado")
        self.inference_info.set("Análise parada. Nenhum sinal é mantido.")

    def connect(self):
        if self.reader and self.reader.thread.is_alive():
            self.camera_status.set("Aguarde a conexão anterior encerrar. Se necessário, reabra o programa.")
            return
        try:
            index = int(self.index.get())
            if index < 0:
                raise ValueError
        except ValueError:
            self.camera_status.set("Informe um índice de câmera inteiro a partir de 0.")
            return
        self.stop_test()
        self.reader = CameraReader(index)
        self.connected = True
        self.rendered = 0.0
        self.index_input.configure(state="disabled")
        self.connect_button.configure(state="disabled")
        self.disconnect_button.configure(state="normal")
        self.reader.start()

    def disconnect(self):
        self.stop_test()
        self.connected = False
        if self.reader:
            self.reader.stop.set()
        self.preview.configure(image="", text="Câmera desconectada.")
        self.photo = None
        self.index_input.configure(state="normal")
        self.connect_button.configure(state="normal")
        self.disconnect_button.configure(state="disabled")
        self.test_button.configure(state="disabled")
        self.camera_status.set("Câmera desconectada")

    def fresh_frame(self):
        if not self.connected or not self.reader or self.reader.stop.is_set():
            return None
        frame, timestamp, _ = self.reader.snapshot()
        return frame if frame is not None and time.monotonic() - timestamp <= FRESH_SECONDS else None

    def toggle_test(self):
        if self.running:
            self.stop_test()
            return
        if self.fresh_frame() is None:
            self.inference_info.set("Conecte a câmera e aguarde a imagem antes de iniciar o teste.")
            return
        self.gate.reset()
        self.running = True
        self.worker.configure(self.reader)
        self.test_button.configure(text="Parar teste")
        self.set_signal("amber", "Analisando")

    def render_frame(self, frame):
        height, width = frame.shape[:2]
        scale = min(660 / width, 390 / height, 1)
        image = cv2.resize(frame, (max(1, int(width * scale)), max(1, int(height * scale))))
        ok, encoded = cv2.imencode(".png", image)
        if not ok:
            raise RuntimeError("Falha ao preparar prévia.")
        self.photo = tk.PhotoImage(master=self.root, data=base64.b64encode(encoded.tobytes()))
        self.preview.configure(image=self.photo, text="")

    def tick(self):
        try:
            fresh = self.fresh_frame()
            if self.connected and self.reader:
                frame, timestamp, status = self.reader.snapshot()
                if fresh is not None and frame is not None:
                    if timestamp != self.rendered:
                        self.render_frame(frame)
                        self.rendered = timestamp
                    self.camera_status.set(f"Câmera conectada • {frame.shape[1]} × {frame.shape[0]} pixels")
                else:
                    self.camera_status.set(status if frame is None else "Sem quadros recentes.")
                    self.preview.configure(image="", text=self.camera_status.get())
                    self.photo = None
                    self.rendered = 0.0
                    if not self.reader.thread.is_alive():
                        self.connect_button.configure(state="normal")
                        self.index_input.configure(state="normal")
                self.test_button.configure(state="normal" if fresh is not None or self.running else "disabled")
            if self.running:
                result = self.worker.snapshot()
                if fresh is None or result is None:
                    self.gate.reset()
                    self.set_signal("amber", "Aguardando imagem e análise recentes")
                    self.inference_info.set("Sem resultado recente.")
                else:
                    captured_at, prediction, duration = result
                    color = self.gate.update(prediction.label, captured_at, green_enabled=True)
                    detail = "Confirmando posição" if color == "amber" and prediction.label == "abaixada" else ""
                    if time.monotonic() - captured_at > FRESH_SECONDS:
                        detail = "Análise atrasada"
                    self.set_signal(color, detail)
                    self.inference_info.set(f"{prediction.reason} | Análise: {duration:.0f} ms")
        except (cv2.error, tk.TclError, RuntimeError, ValueError) as exc:
            self.disconnect()
            self.inference_info.set(f"Falha na prévia: {exc}")
        self.timer = self.root.after(60, self.tick)

    def close(self):
        self.worker.close()
        if self.reader:
            self.reader.stop.set()
        if self.timer is not None:
            self.root.after_cancel(self.timer)
        self.root.destroy()


def main():
    root = tk.Tk()
    app = HelmetTestApp(root)
    app.tick()
    root.mainloop()


if __name__ == "__main__":
    main()
