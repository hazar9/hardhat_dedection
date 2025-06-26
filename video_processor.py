import cv2
import time
import math
import datetime
import os
from ultralytics import YOLO

import config

class VideoProcessor:
    def __init__(self, app_instance):
        self.app = app_instance 
        self.model = self.app.model
        
    def run(self):
        while not self.app.stop_event.is_set():
            frame_to_process = None
            with self.app.frame_lock:
                if self.app.latest_frame is not None:
                    frame_to_process = self.app.latest_frame.copy()

            if frame_to_process is None:
                time.sleep(0.01)
                continue

            current_threshold = self.app.confidence_var.get()
            
            results = self.model.track(frame_to_process, persist=True, verbose=False)
            
            current_results_data = []
            active_track_ids = set()

            now = time.time()
            self.app.recent_log_zones = [(t, x, y) for t, x, y in self.app.recent_log_zones if now - t < config.LOG_COOLDOWN_SECONDS]

            if results[0].boxes.id is not None:
                boxes = results[0].boxes.xyxy.cpu()
                track_ids = results[0].boxes.id.int().cpu().tolist()
                confs = results[0].boxes.conf.cpu().tolist()
                clss = results[0].boxes.cls.cpu().tolist()
                
                for box, track_id, conf, cls in zip(boxes, track_ids, confs, clss):
                    active_track_ids.add(track_id)
                    is_violation = (int(cls) == config.VIOLATION_CLASS_ID)
                    
                    if (is_violation and 
                        conf >= current_threshold and 
                        track_id not in self.app.logged_tracker_ids):
                        
                        cx, cy = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
                        is_in_cooldown_zone = False
                        for log_time, log_cx, log_cy in self.app.recent_log_zones:
                            distance = math.sqrt((cx - log_cx)**2 + (cy - log_cy)**2)
                            if distance < config.LOG_ZONE_RADIUS:
                                is_in_cooldown_zone = True
                                break
                        
                        if not is_in_cooldown_zone:
                            log_data = [(list(map(int, box)), f"ID:{track_id} | IHLAL")]
                            self.log_violation(frame_to_process, log_data)
                            self.app.logged_tracker_ids.add(track_id)
                            self.app.recent_log_zones.append((time.time(), cx, cy))

                    label = f"ID:{track_id} | {self.model.names[int(cls)]} {conf:.2f}"
                    current_results_data.append({
                        "box": list(map(int, box)),
                        "label": label,
                        "cls_id": int(cls)
                    })

            with self.app.results_lock: self.app.latest_results_for_drawing = current_results_data
    
    def log_violation(self, frame_to_save, results_to_draw):
        now = datetime.datetime.now()
        timestamp_for_file = now.strftime("%Y-%m-%d %H:%M:%S.%f")
        log_image = frame_to_save.copy()

        if self.app.show_boxes_var.get():
            for coords, label in results_to_draw:
                x1, y1, x2, y2 = coords
                cv2.rectangle(log_image, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(log_image, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        filename = f"violation_{now.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        save_path = os.path.join(config.VIOLATION_IMG_DIR, filename)
        jpeg_quality = [cv2.IMWRITE_JPEG_QUALITY, 95]

        if cv2.imwrite(save_path, log_image, jpeg_quality):
            with open(config.LOG_FILE_PATH, "a", encoding="utf-8") as f:
                f.write(f"{timestamp_for_file}|{save_path}\n")
            
            self.app.log_queue.put((now, save_path))

            notification_data = {
                'title': 'Baret İhlali Tespit Edildi!',
                'message': f"Saat {now.strftime('%H:%M:%S')} itibarıyla bir ihlal kaydedildi."
            }
            self.app.notification_queue.put(notification_data)