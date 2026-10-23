"""Abra com python teste_combinado.py. Mostra máscara, luva e avental ao mesmo tempo
e a combinação deles. Ensaio visual local, sem treino e sem sinalização física."""
import base64
import time
import tkinter as tk
from tkinter import ttk

import cv2

from color_presence import CombinationDetector
from helmet_experiment import FRESH_SECONDS, Prediction, SignalGate
from mask_state import FaceMaskDetector
from overlay import draw_regions
from teste_mascara import AnalysisWorker
from tirar_foto import CameraReader

ITEMS = ("mascara", "luva", "avental")
NAMES = {"mascara": "Máscara", "luva": "Luva", "avental": "Avental"}
# Mensagem quando o item está comprovadamente fora do padrão.
PROBLEM = {"mascara": "máscara levantada", "luva": "sem luva", "avental": "sem avental"}
OK_TEXT = {"mascara": "abaixada", "luva": "com luva", "avental": "com avental"}
BAD_TEXT = {"mascara": "levantada", "luva": "sem luva", "avental": "sem avental"}
# O SignalGate confirma "abaixada" (verde) por 3 quadros e 0,5 s e mostra "levantada"
# (vermelho) na hora; aqui verde = item correto e vermelho = item fora do padrão.
GATE_LABEL = {"levantada": "levantada", "abaixada": "abaixada", "com": "abaixada", "sem": "levantada"}
COLORS = {"red": ("#fee2e2", "#991b1b"), "green": ("#dcfce7", "#166534"),
          "amber": ("#fef3c7", "#92400e")}


class CombinedDetector:
    """Analisa o mesmo quadro com os três detectores; uma falha afeta só o seu item."""

    def __init__(self):
        self.mask = FaceMaskDetector()
        self.combo = CombinationDetector(("luva", "avental"))

    def predict(self, frame):
        results = {}
        for items, detector in ((("mascara",), self.mask), (("luva", "avental"), self.combo)):
            try:
                found = detector.predict(frame)
                results.update(found if isinstance(found, dict) else {items[0]: found})
            except Exception as exc:
                failure = Prediction("inconclusiva", 0.0, 0.0, f"Falha de análise: {exc}")
                results.update({item: failure for item in items})
        return results


def combine(colors):
    """Vermelho se algum item está fora do padrão; verde só com os três corretos."""
    if "red" in colors.values():
        return "red"
    return "green" if all(color == "green" for color in colors.values()) else "amber"


class CombinedTestApp:
    def __init__(self, root):
        self.root = root
        self.reader = None
        self.connected = False
        self.running = False
        self.photo = None
        self.rendered = 0.0
        self.timer = None
        self.gates = {item: SignalGate() for item in ITEMS}
        self.detector = CombinedDetector()
        self.worker = AnalysisWorker(self.detector)
        root.title("TecnoSolda | Teste combinado de EPIs")
        root.geometry("780x960")
        root.minsize(720, 900)
        root.protocol("WM_DELETE_WINDOW", self.close)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#eef2f6")
        style.configure("TLabel", background="#eef2f6", foreground="#14253b", font=("Segoe UI", 10))
        style.configure("TButton", padding=6, font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 21, "bold"))
        page = ttk.Frame(root, padding=18)
        page.pack(fill="both", expand=True)
        ttk.Label(page, text="Teste combinado de EPIs", style="Title.TLabel").pack(anchor="w")
        ttk.Label(page, text="Máscara + luva + avental • Calibração ao vivo • Sem acionamento físico").pack(anchor="w", pady=(3, 10))
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

        view = tk.Frame(page, bg="#101b2c", height=260)
        view.pack(fill="both", expand=True, pady=10)
        view.pack_propagate(False)
        self.preview = tk.Label(view, bg="#101b2c", fg="#d8e1ee", font=("Segoe UI", 12),
                                text="Conecte a câmera para começar.")
        self.preview.pack(fill="both", expand=True)
        status_row = ttk.Frame(page)
        status_row.pack(fill="x")
        self.camera_status = tk.StringVar(value="Câmera desconectada")
        ttk.Label(status_row, textvariable=self.camera_status, wraplength=520).pack(side="left")
        self.show_trace = tk.BooleanVar(value=True)
        ttk.Checkbutton(status_row, text="Mostrar o que está sendo identificado",
                        variable=self.show_trace).pack(side="right")
        self.trace_text = tk.StringVar(value="Marcado na imagem: nada (inicie o teste)")
        ttk.Label(page, textvariable=self.trace_text, wraplength=720).pack(anchor="w", pady=(2, 0))

        cards = ttk.Frame(page)
        cards.pack(fill="x", pady=(10, 0))
        self.cards = {}
        for item in ITEMS:
            card = tk.Label(cards, font=("Segoe UI", 11, "bold"), padx=8, pady=10, wraplength=220)
            card.pack(side="left", fill="x", expand=True, padx=(0, 6))
            self.cards[item] = card
        self.signal = tk.Label(page, font=("Segoe UI", 17, "bold"), padx=10, pady=14, wraplength=700)
        self.signal.pack(fill="x", pady=(10, 6))
        self.inference_info = tk.StringVar(value="Conecte a câmera, calibre luva e avental e inicie o teste.")
        ttk.Label(page, textvariable=self.inference_info, wraplength=720).pack(anchor="w")

        ttk.Label(page, text="Calibração por combinação (a máscara não precisa)",
                  font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(12, 4))
        grid = ttk.Frame(page)
        grid.pack(fill="x")
        self.calibrate_buttons = []
        self.combo_texts = {}
        for position, key in enumerate(self.detector.combo.keys):
            text = tk.StringVar()
            button = ttk.Button(grid, textvariable=text, state="disabled",
                                command=lambda k=key: self.calibrate(k))
            button.grid(row=position // 2, column=position % 2, sticky="ew", padx=(0, 8), pady=3)
            grid.columnconfigure(position % 2, weight=1)
            self.calibrate_buttons.append(button)
            self.combo_texts[key] = text
        ttk.Button(page, text="Limpar calibração", command=self.clear_calibration).pack(anchor="w", pady=(6, 0))
        ttk.Label(page, wraplength=720, text=(
            "Com a máscara abaixada, vista exatamente a combinação do botão e clique 3 a 5 vezes, "
            "variando levemente a posição. Faça as quatro combinações e recalibre se a luz mudar.\n"
            "Verde geral: máscara abaixada, com luva e com avental, estáveis por 0,5 s. "
            "Vermelho: algum item fora do padrão. Amarelo: algum item indefinido. "
            "O verde é só indicação neste ensaio; não libera soldagem.")).pack(anchor="w", pady=(10, 0))
        self.update_calibration_text()
        self.show_idle("Teste parado")

    def update_calibration_text(self):
        for key, text in self.combo_texts.items():
            title = " + ".join(f"{'COM' if kind == 'com' else 'SEM'} {item}"
                               for item, kind in zip(self.detector.combo.items, key))
            text.set(f"{title}  ({self.detector.combo.counts[key]})")

    def show_item(self, item, color, text):
        bg, fg = COLORS[color]
        self.cards[item].configure(text=f"{NAMES[item]}\n{text}", bg=bg, fg=fg)

    def show_overall(self, color, detail=""):
        titles = {"red": "VERMELHO • EPI fora do padrão", "green": "VERDE • Combinação correta",
                  "amber": "INCONCLUSIVO"}
        bg, fg = COLORS[color]
        self.signal.configure(text=titles[color] + (f" • {detail}" if detail else ""), bg=bg, fg=fg)

    def show_idle(self, detail):
        for item in ITEMS:
            self.show_item(item, "amber", "—")
        self.show_overall("amber", detail)

    def stop_test(self):
        self.running = False
        self.worker.configure()
        for gate in self.gates.values():
            gate.reset()
        self.test_button.configure(text="Iniciar teste")
        self.show_idle("Teste parado")
        self.inference_info.set("Análise parada. Nenhum sinal é mantido.")

    def reset_gates(self):
        for gate in self.gates.values():
            gate.reset()

    def calibrate(self, key):
        frame = self.fresh_frame()
        if frame is None:
            self.inference_info.set("Sem imagem recente. Conecte a câmera antes de calibrar.")
            return
        self.detector.combo.add_sample(key, frame)
        self.reset_gates()
        self.update_calibration_text()

    def clear_calibration(self):
        self.detector.combo.reset()
        self.reset_gates()
        self.update_calibration_text()

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
        for button in self.calibrate_buttons:
            button.configure(state="disabled")
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
        self.reset_gates()
        self.running = True
        self.worker.configure(self.reader)
        self.test_button.configure(text="Parar teste")
        self.show_idle("Analisando")

    def render_frame(self, frame, regions=()):
        height, width = frame.shape[:2]
        scale = min(700 / width, 250 / height, 1)
        image = cv2.resize(frame, (max(1, int(width * scale)), max(1, int(height * scale))))
        draw_regions(image, regions)
        ok, encoded = cv2.imencode(".png", image)
        if not ok:
            raise RuntimeError("Falha ao preparar prévia.")
        self.photo = tk.PhotoImage(master=self.root, data=base64.b64encode(encoded.tobytes()))
        self.preview.configure(image=self.photo, text="")

    def update_signals(self, captured_at, predictions):
        colors = {}
        for item in ITEMS:
            label = GATE_LABEL.get(predictions[item].label)
            colors[item] = self.gates[item].update(label, captured_at, green_enabled=True)
            text = {"green": OK_TEXT[item], "red": BAD_TEXT[item]}.get(colors[item], "indefinido")
            self.show_item(item, colors[item], text)
        overall = combine(colors)
        pending = [PROBLEM[i] if colors[i] == "red" else f"{NAMES[i].lower()} indefinido"
                   for i in ITEMS if colors[i] != "green"]
        stale = time.monotonic() - captured_at > FRESH_SECONDS
        self.show_overall(overall, "Análise atrasada" if stale else ", ".join(pending))

    def current_regions(self, result):
        """Regiões da análise mais recente, só enquanto ela estiver fresca e o usuário quiser vê-las."""
        if not (self.running and self.show_trace.get()) or result is None:
            return ()
        if time.monotonic() - result[0] > FRESH_SECONDS:
            return ()
        return tuple(region for prediction in result[1].values() for region in prediction.regions)

    def tick(self):
        try:
            fresh = self.fresh_frame()
            result = self.worker.snapshot() if self.running else None
            regions = self.current_regions(result)
            self.trace_text.set("Marcado na imagem: " + (
                ", ".join(region.text for region in regions) if regions
                else "nada" if self.running and self.show_trace.get() else "nada (inicie o teste)"))
            if self.connected and self.reader:
                frame, timestamp, status = self.reader.snapshot()
                if fresh is not None and frame is not None:
                    if timestamp != self.rendered:
                        self.render_frame(frame, regions)
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
                for button in self.calibrate_buttons:
                    button.configure(state="normal" if fresh is not None else "disabled")
            if self.running:
                if fresh is None or result is None:
                    self.reset_gates()
                    self.show_idle("Aguardando imagem e análise recentes")
                    self.inference_info.set("Sem resultado recente.")
                else:
                    captured_at, predictions, duration = result
                    self.update_signals(captured_at, predictions)
                    self.inference_info.set(
                        " | ".join(f"{NAMES[i]}: {predictions[i].reason}" for i in ITEMS)
                        + f" | Análise: {duration:.0f} ms")
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
    app = CombinedTestApp(root)
    app.tick()
    root.mainloop()


if __name__ == "__main__":
    main()
