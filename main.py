import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
from PIL import Image, ImageTk
import cv2
import os
import datetime
import threading
import time
from queue import Queue
import math

import config
from ui_manager import UIManager
from video_processor import VideoProcessor
from ultralytics import YOLO
from plyer import notification

class HardHatApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Baret Takip Sistemi")
        
        self.state('zoomed') 
        self.minsize(1280, 720)

        self.setup_theme()

        self.cap = None
        self.all_logs = []
        self.log_map = {}
        
        self.frame_lock = threading.Lock()
        self.results_lock = threading.Lock()
        self.latest_frame = None
        self.latest_results_for_drawing = []
        self.stop_event = threading.Event()
        self.log_queue = Queue()
        self.notification_queue = Queue()
        self.processing_thread = None
        self.display_job = None
        
        self.video_delay = 15
        self.last_notification_time = 0

        self.logged_tracker_ids = set()
        self.recent_log_zones = []
        
        self.confidence_var = tk.DoubleVar(value=config.DEFAULT_CONFIDENCE)
        self.show_boxes_var = tk.BooleanVar(value=True)
        self.show_helmets_var = tk.BooleanVar(value=True)
        
        self.log_count_var = tk.StringVar(value="Görüntülenen Kayıt: 0")
        
        os.makedirs(config.VIOLATION_IMG_DIR, exist_ok=True)
        
        self.model = self.load_model()
        self.ui = UIManager(self)
        self.load_logs_from_disk()
        self.check_log_queue()
        self.check_notification_queue()

    def setup_theme(self):
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            theme_file = os.path.join(script_dir, "theme", "azure.tcl")
            if os.path.exists(theme_file):
                self.tk.call("source", theme_file)
                self.tk.call("set_theme", "dark")
            else:
                 print(f"Uyarı: Azure tema dosyası bulunamadı. Lütfen 'theme/azure.tcl' yolunu kontrol edin.")
        except Exception as e:
            print(f"Tema yüklenirken hata oluştu: {e}")

    def load_model(self):
        if not os.path.exists(config.MODEL_PATH):
            messagebox.showerror("Hata", f"Model dosyası bulunamadı: {config.MODEL_PATH}")
            self.quit()
        try:
            return YOLO(config.MODEL_PATH)
        except Exception as e:
            messagebox.showerror("Model Yükleme Hatası", f"Model yüklenirken bir hata oluştu: {e}")
            self.quit()


    def open_settings_window(self):
        if hasattr(self, 'settings_window') and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return

        self.settings_window = tk.Toplevel(self)
        self.settings_window.title("Gelişmiş Ayarlar")
        self.settings_window.geometry("320x220")
        self.settings_window.resizable(False, False)
        self.settings_window.transient(self) 

        settings_frame = ttk.Frame(self.settings_window, padding=15)
        settings_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(settings_frame, text="Güven Eşiği (Confidence):").pack(anchor='w')
        confidence_scale = ttk.Scale(settings_frame, from_=0.10, to=0.95, orient=tk.HORIZONTAL, variable=self.confidence_var, length=280)
        confidence_scale.pack(fill=tk.X, pady=(5, 15))
        try:
            show_boxes_check = ttk.Checkbutton(settings_frame, text="Tespit Kutucuklarını Göster", variable=self.show_boxes_var, style='Switch.TCheckbutton')
            helmet_frame = ttk.Frame(settings_frame)
            show_helmets_check = ttk.Checkbutton(helmet_frame, text="Kask Takanları Göster", variable=self.show_helmets_var, style='Switch.TCheckbutton')

        except tk.TclError:
            show_boxes_check = ttk.Checkbutton(settings_frame, text="Tespit Kutucuklarını Göster", variable=self.show_boxes_var)
            helmet_frame = ttk.Frame(settings_frame)
            show_helmets_check = ttk.Checkbutton(helmet_frame, text="Kask Takanları Göster", variable=self.show_helmets_var)
        
        show_boxes_check.pack(anchor='w', pady=5)
        
        helmet_frame.pack(fill=tk.X, padx=(20, 0), pady=0)
        show_helmets_check.pack(anchor='w')

        def update_helmet_checkbox_state():
            if self.show_boxes_var.get():
                show_helmets_check.config(state=tk.NORMAL)
            else:
                show_helmets_check.config(state=tk.DISABLED)
        show_boxes_check.config(command=update_helmet_checkbox_state)
        update_helmet_checkbox_state()

    def connect_ip_camera(self):
        url = simpledialog.askstring("IP Kamera Bağlantısı", "Lütfen kamera URL'sini girin (örn: rtsp://...):", parent=self)
        if url:
            self.start_processing_loop(url)
            
    def start_processing_loop(self, source):
        self.stop_processing()

        if isinstance(source, int):
            self.cap = cv2.VideoCapture(source, cv2.CAP_DSHOW)
        else:
            self.cap = cv2.VideoCapture(source)

        if not self.cap.isOpened():
            messagebox.showerror("Hata", f"Kaynak açılamadı: {source}")
            self.stop_processing()
            return
            
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        
        if fps > 0:
            self.video_delay = int(1000 / fps)
        else:
            self.video_delay = 15 
        
        self.stop_event.clear()
        
        processor = VideoProcessor(self)
        self.processing_thread = threading.Thread(target=processor.run, daemon=True)
        self.processing_thread.start()
        
        self.display_loop()
        
        self.ui.btn_select_video.config(state=tk.DISABLED)
        self.ui.btn_select_camera.config(state=tk.DISABLED)
        self.ui.btn_connect_ip_camera.config(state=tk.DISABLED)
        self.ui.btn_stop.config(state=tk.NORMAL)

    def stop_processing(self):
        self.stop_event.set()

        if self.display_job: 
            self.after_cancel(self.display_job)
        self.display_job = None

        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=1)
        self.processing_thread = None

        if self.cap:
            self.cap.release()
        self.cap = None

        with self.frame_lock:
            self.latest_frame = None
        with self.results_lock:
            self.latest_results_for_drawing.clear()
        
        self.logged_tracker_ids.clear()
        self.recent_log_zones.clear()
        
        self.ui.btn_select_video.config(state=tk.NORMAL)
        self.ui.btn_select_camera.config(state=tk.NORMAL)
        self.ui.btn_connect_ip_camera.config(state=tk.NORMAL)
        self.ui.btn_stop.config(state=tk.DISABLED)
        self.ui.image_label.config(image=None, text="")

    def display_loop(self):
        if self.stop_event.is_set(): return
        if not self.cap or not self.cap.isOpened():
            self.stop_processing()
            return
            
        ret, frame = self.cap.read()
        if not ret:
            self.stop_processing()
            return
        
        with self.frame_lock: self.latest_frame = frame
        
        if self.show_boxes_var.get():
            with self.results_lock: results_to_draw = list(self.latest_results_for_drawing)
            
            show_helmets = self.show_helmets_var.get()

            for result in results_to_draw:
                x1, y1, x2, y2 = result["box"]
                cls_id = result["cls_id"]
                label = result["label"]
                
                if cls_id == config.VIOLATION_CLASS_ID:
                    color = (0, 0, 255)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                elif show_helmets and cls_id == config.HELMET_CLASS_ID:
                    color = (0, 255, 0)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        self.update_image_display(frame)
        
        self.display_job = self.after(self.video_delay, self.display_loop)
            
    def check_log_queue(self):
        try:
            while not self.log_queue.empty():
                datetime_obj, save_path = self.log_queue.get_nowait()
                self.all_logs.insert(0, (datetime_obj, save_path))
                self.filter_logs() 
        finally:
            self.after(200, self.check_log_queue)
            
    def check_notification_queue(self):
        try:
            if not self.notification_queue.empty():
                current_time = time.time()
                
                if (current_time - self.last_notification_time) > config.NOTIFICATION_COOLDOWN_SECONDS:
                    notification_data = self.notification_queue.get_nowait()
                    
                    notification.notify(
                        title=notification_data['title'],
                        message=notification_data['message'],
                        app_name='Baret Takip Sistemi',
                        timeout=10
                    )
                    
                    self.last_notification_time = current_time
                else:
                    while not self.notification_queue.empty():
                        self.notification_queue.get_nowait()

        except Exception as e:
            print(f"Bildirim kuyruğu işlenirken hata: {e}")
        finally:
            self.after(500, self.check_notification_queue)

    def clear_logs(self):
        if not self.all_logs:
            messagebox.showinfo("Bilgi", "Temizlenecek log bulunmuyor.")
            return
        if messagebox.askyesno("Onay", "Tüm ihlal kayıtları ve fotoğraflar kalıcı olarak silinecektir. Emin misiniz?"):
            try:
                self.all_logs.clear()
                self.log_map.clear()
                self.ui.log_listbox.delete(0, tk.END)
                self.update_log_count()
                
                self.logged_tracker_ids.clear()
                self.recent_log_zones.clear()
                with open(config.LOG_FILE_PATH, 'w') as f: pass
                for filename in os.listdir(config.VIOLATION_IMG_DIR):
                    file_path = os.path.join(config.VIOLATION_IMG_DIR, filename)
                    if os.path.isfile(file_path): os.unlink(file_path)
                messagebox.showinfo("Başarılı", "Tüm loglar ve ihlal fotoğrafları başarıyla temizlendi.")
            except Exception as e: messagebox.showerror("Hata", f"Loglar temizlenirken bir hata oluştu: {e}")
    
    def format_datetime_for_display(self, dt_obj):
        month_name = config.TURKISH_MONTHS[dt_obj.month - 1]
        return f"Tarih: {dt_obj.day} {month_name} {dt_obj.year}, Saat: {dt_obj.strftime('%H:%M:%S')}"

    def filter_logs(self, days=None):
        self.ui.log_listbox.delete(0, tk.END)
        self.log_map.clear()
        
        cutoff_date = None
        if days is not None:
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)
            
        filtered_logs = [log for log in self.all_logs if cutoff_date is None or log[0] > cutoff_date]
            
        for dt_obj, path in filtered_logs:
            display_str = self.format_datetime_for_display(dt_obj)
            self.ui.log_listbox.insert(tk.END, display_str)
            self.log_map[display_str] = path
            
        self.update_log_count()

    def update_log_count(self):
        count = self.ui.log_listbox.size()
        self.log_count_var.set(f"Görüntülenen Kayıt: {count}")
            
    def load_logs_from_disk(self):
        if not os.path.exists(config.LOG_FILE_PATH): return
        
        with open(config.LOG_FILE_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if "|" in line:
                    try:
                        timestamp_str, image_path = line.strip().split("|")
                        dt_obj = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f")
                        if os.path.exists(image_path):
                            self.all_logs.append((dt_obj, image_path))
                    except (ValueError, IndexError):
                        print(f"Hatalı log satırı atlanıyor: {line.strip()}")
                        continue
        
        self.all_logs.sort(key=lambda x: x[0], reverse=True)
        self.filter_logs()
    
    def select_video_file(self):
        path = filedialog.askopenfilename(filetypes=[("Video Dosyaları", "*.mp4 *.avi *.mov *.mkv")])
        if path: self.start_processing_loop(path)
        
    def start_camera(self):
        self.start_processing_loop(0)
        
    def update_image_display(self, cv2_image):
        container_w = self.ui.image_label.winfo_width()
        container_h = self.ui.image_label.winfo_height()
        if container_h > 1 and container_w > 1:
            img_h, img_w, _ = cv2_image.shape
            scale = min(container_w / img_w, container_h / img_h)
            if scale < 1.0: 
                resized_image = cv2.resize(cv2_image, (int(img_w * scale), int(img_h * scale)), interpolation=cv2.INTER_AREA)
            else: 
                resized_image = cv2_image
            img_rgb = cv2.cvtColor(resized_image, cv2.COLOR_BGR2RGB)
            tk_img = ImageTk.PhotoImage(image=Image.fromarray(img_rgb))
            self.ui.image_label.config(image=tk_img)
            self.ui.image_label.image = tk_img
            
    def show_violation_in_new_window(self, event):
        selected_indices = self.ui.log_listbox.curselection()
        if not selected_indices: return
        
        log_entry_key = self.ui.log_listbox.get(selected_indices[0])
        image_path = self.log_map.get(log_entry_key)
        
        if not image_path or not os.path.exists(image_path):
            messagebox.showwarning("Uyarı", f"Görüntü dosyası bulunamadı:\n{image_path}")
            return
        
        violation_window = tk.Toplevel(self)
        violation_window.title(f"İhlal Anı: {log_entry_key}")

        try:
            img = cv2.imread(image_path)
            img_h, img_w, _ = img.shape

            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            max_w = int(screen_w * 0.8)
            max_h = int(screen_h * 0.8)

            scale = min(max_w / img_w, max_h / img_h)
            new_w = int(img_w * scale)
            new_h = int(img_h * scale)
            
            resized_image = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

            img_rgb = cv2.cvtColor(resized_image, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
            tk_img = ImageTk.PhotoImage(image=pil_img)

            img_label = ttk.Label(violation_window, image=tk_img)
            img_label.pack()
            img_label.image = tk_img 
            
            pos_x = (screen_w // 2) - (new_w // 2)
            pos_y = (screen_h // 2) - (new_h // 2)
            violation_window.geometry(f"{new_w}x{new_h}+{pos_x}+{pos_y}")
            violation_window.resizable(False, False)

        except Exception as e:
            violation_window.destroy()
            messagebox.showerror("Görüntü Hatası", f"Görüntü yüklenirken bir hata oluştu: {e}")
            
    def on_closing(self):
        self.stop_processing()
        self.destroy()

if __name__ == "__main__":
    app = HardHatApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()