import tkinter as tk
from tkinter import ttk

class UIManager:
    def __init__(self, app_instance):
        self.app = app_instance
        self.setup_ui()

    def setup_ui(self):
        style = ttk.Style(self.app)
        style.configure('Accent.TButton', foreground='white')
        style.configure('Danger.TButton', foreground='white')

        main_frame = ttk.Frame(self.app, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        paned_window = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True)

        #sol panel
        left_pane = ttk.Frame(paned_window) 
        paned_window.add(left_pane, weight=5) 
        
        self.image_label = ttk.Label(left_pane, background="black", anchor="center")
        self.image_label.pack(fill=tk.BOTH, expand=True)

        #sag panel
        right_pane = ttk.Frame(paned_window)
        paned_window.add(right_pane, weight=1)

        #butonlar
        control_frame = ttk.LabelFrame(right_pane, text="Kontrol Paneli", padding=10)
        control_frame.pack(fill=tk.X, pady=5)
        
        self.btn_select_video = ttk.Button(control_frame, text="Video Dosyası Seç", command=self.app.select_video_file, style='Accent.TButton')
        self.btn_select_video.pack(fill=tk.X, pady=4)
        
        self.btn_select_camera = ttk.Button(control_frame, text="Canlı Kamerayı Başlat", command=self.app.start_camera, style='Accent.TButton')
        self.btn_select_camera.pack(fill=tk.X, pady=4)

        self.btn_connect_ip_camera = ttk.Button(control_frame, text="IP Kamera Bağlan", command=self.app.connect_ip_camera, style='Accent.TButton')
        self.btn_connect_ip_camera.pack(fill=tk.X, pady=4)

        self.btn_stop = ttk.Button(control_frame, text="İşlemi Durdur", command=self.app.stop_processing, state=tk.DISABLED)
        self.btn_stop.pack(fill=tk.X, pady=4)
        
        self.btn_settings = ttk.Button(control_frame, text="Gelişmiş Ayarlar", command=self.app.open_settings_window)
        self.btn_settings.pack(fill=tk.X, pady=(15, 4))

        log_container = ttk.LabelFrame(right_pane, text="İhlal Kayıtları", padding=10)
        log_container.pack(fill=tk.BOTH, expand=True, pady=10)
        
        filter_frame = ttk.Frame(log_container)
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        #log gunlugu
        filter_buttons = {"Tümü": None, "1 Gün": 1, "3 Gün": 3, "7 Gün": 7, "30 Gün": 30}
        for text, days in filter_buttons.items():
            btn = ttk.Button(filter_frame, text=text, command=lambda d=days: self.app.filter_logs(d))
            btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=1)

        log_list_frame = ttk.Frame(log_container)
        log_list_frame.pack(fill=tk.BOTH, expand=True)
        self.log_listbox = tk.Listbox(log_list_frame, background="#313131", foreground="white", selectbackground="#0078d4", borderwidth=0, highlightthickness=0)
        self.log_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(log_list_frame, orient=tk.VERTICAL, command=self.log_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_listbox.config(yscrollcommand=scrollbar.set)
        self.log_listbox.bind("<<ListboxSelect>>", self.app.show_violation_in_new_window)
        
        log_footer_frame = ttk.Frame(log_container)
        log_footer_frame.pack(fill=tk.X, pady=(5,0))
        
        self.log_count_label = ttk.Label(log_footer_frame, textvariable=self.app.log_count_var)
        self.log_count_label.pack(side=tk.LEFT)

        self.btn_clear_logs = ttk.Button(log_footer_frame, text="Temizle", command=self.app.clear_logs, style='Danger.TButton')
        self.btn_clear_logs.pack(side=tk.RIGHT)