import os

#paths
MODEL_PATH = "models/best.pt"
LOG_DIR = "log"
VIOLATION_IMG_DIR = os.path.join(LOG_DIR, "violations")
LOG_FILE_PATH = os.path.join(LOG_DIR, "violations.log")

#parametreler - gelismis ayarlar icin
DEFAULT_CONFIDENCE = 0.55 
VIOLATION_CLASS_ID = 0 
HELMET_CLASS_ID = 1

#zone ayarlari
LOG_COOLDOWN_SECONDS = 10.0 
LOG_ZONE_RADIUS = 75

#bildirim cooldown
NOTIFICATION_COOLDOWN_SECONDS = 10


TURKISH_MONTHS = (
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"
)