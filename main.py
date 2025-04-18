import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
import random
from datetime import datetime, timedelta

# Logging ayarları
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot tokenını buraya ekleyin
TOKEN = "8026541050:AAEfrfEPvy3Ep5V4NSbQcw4zTJhQ89d9VmY"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin321"

# Ödeme yöntemleri (Admin panelinden eklenip kaldırılabilir)
PAYMENT_METHODS = ["Banka Havalesi", "Papara", "Kripto Para"]

# Fiyatlar
PRICES = {
    "daily": {"tl": 30, "usd": 1},
    "weekly": {"tl": 200, "usd": 6},
    "monthly": {"tl": 500, "usd": 15},
    "yearly": {"tl": 1500, "usd": 45}
}

# Verileri saklamak için basit bir yapı
class Database:
    def __init__(self):
        self.users = {}  # {user_id: {"membership_end": date, "used_profiles": set(), "referrals": int}}
        self.pending_payments = []  # {"user_id": int, "amount": float, "type": str, "receipt": str, "method": str}
        self.fake_profiles = self.generate_realistic_turkish_profiles()
        self.admin_password = ADMIN_PASSWORD
        self.payment_methods = PAYMENT_METHODS.copy()
    
    def generate_realistic_turkish_profiles(self):
        # 500 gerçekçi Türk kullanıcı profili
        first_names = ["Ahmet", "Mehmet", "Ayşe", "Fatma", "Ali", "Veli", "Zeynep", "Elif", "Mustafa", "Emre", 
                      "Berk", "Can", "Deniz", "Ece", "Furkan", "Gizem", "Hakan", "Irmak", "Jale", "Kemal"]
        last_names = ["Yılmaz", "Kaya", "Demir", "Çelik", "Şahin", "Yıldız", "Arslan", "Koç", "Taş", "Kurt",
                     "Aksoy", "Barış", "Ceylan", "Dal", "Erdoğan", "Fırat", "Güneş", "Hazar", "Işık", "Jandarma"]
        
        common_words = ["sevgili", "ask", "love", "hayat", "gece", "gunduz", "yasam", "mutlu", "huzur", "kalp",
                       "gizem", "sır", "bilinmez", "kahve", "cay", "tatli", "acı", "mutfak", "seyahat", "macera"]
        
        profiles = []
        for i in range(500):
            # Rastgele kullanıcı adı oluşturma stratejileri
            if random.random() < 0.3:
                username = f"{random.choice(first_names).lower()}_{random.choice(last_names).lower()}"
            elif random.random() < 0.6:
                username = f"{random.choice(first_names).lower()}{random.choice(last_names).lower()}"
            else:
                username = f"{random.choice(common_words)}_{random.randint(10, 999)}"
            
            # Bazı kullanıcı adlarına nokta veya alt çizgi ekle
            if random.random() < 0.2:
                username = username.replace("_", ".")
            
            name = f"{random.choice(first_names)} {random.choice(last_names)}"
            profiles.append({"id": i+1, "username": username, "name": name})
        return profiles
    
    def get_user(self, user_id):
        if user_id not in self.users:
            self.users[user_id] = {
                "membership_end": None,
                "used_profiles": set(),
                "referrals": 0,
                "banned": False
            }
        return self.users[user_id]
    
    def get_unused_profiles(self, user_id, count):
        user = self.get_user(user_id)
        available = [p for p in self.fake_profiles if p["id"] not in user["used_profiles"]]
        
        if not available:
            # Tüm profiller kullanılmışsa, kullanıcının kullanılmış profiller listesini sıfırla
            user["used_profiles"] = set()
            available = self.fake_profiles.copy()
        
        selected = random.sample(available, min(count, len(available)))
        
        # Seçilen profilleri kullanıldı olarak işaretle
        for profile in selected:
            user["used_profiles"].add(profile["id"])
        
        return selected
    
    def add_payment(self, user_id, amount, payment_type, receipt, method):
        self.pending_payments.append({
            "user_id": user_id,
            "amount": amount,
            "type": payment_type,
            "receipt": receipt,
            "method": method,
            "approved": False
        })
    
    def get_pending_payments(self):
        return [p for p in self.pending_payments if not p["approved"]]
    
    def approve_payment(self, payment_index):
        if 0 <= payment_index < len(self.pending_payments):
            payment = self.pending_payments[payment_index]
            payment["approved"] = True
            
            user = self.get_user(payment["user_id"])
            duration = {
                "daily": timedelta(days=1),
                "weekly": timedelta(weeks=1),
                "monthly": timedelta(days=30),
                "yearly": timedelta(days=365)
            }.get(payment["type"], timedelta())
            
            if user["membership_end"] and user["membership_end"] > datetime.now():
                user["membership_end"] += duration
            else:
                user["membership_end"] = datetime.now() + duration
            
            return True
        return False
    
    def reject_payment(self, payment_index):
        if 0 <= payment_index < len(self.pending_payments):
            self.pending_payments.pop(payment_index)
            return True
        return False
    
    def add_payment_method(self, method):
        if method not in self.payment_methods:
            self.payment_methods.append(method)
            return True
        return False
    
    def remove_payment_method(self, method):
        if method in self.payment_methods:
            self.payment_methods.remove(method)
            return True
        return False

# Global database nesnesi
db = Database()

def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if user_data["banned"]:
        update.message.reply_text("⛔ Hesabınız yasaklanmıştır. Admin ile iletişime geçin.")
        return
    
    keyboard = [
        [InlineKeyboardButton("🔍 Stalklayanları Gör", callback_data='show_stalkers')],
        [InlineKeyboardButton("💳 Üyelik Satın Al", callback_data='buy_membership')],
        [InlineKeyboardButton("👥 Referans Bilgileri", callback_data='referral_info')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        f"👋 Merhaba {user.first_name}!\n\n"
        "📱 Bu bot ile Instagram'da seni stalklayanları görebilirsin!\n"
        "🔍 İlk sorgun ücretsiz, sonrası için üyelik satın almalısın.",
        reply_markup=reply_markup
    )

def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()
    user_id = query.from_user.id
    user_data = db.get_user(user_id)
    
    if user_data["banned"]:
        query.edit_message_text("⛔ Hesabınız yasaklanmıştır. Admin ile iletişime geçin.")
        return
    
    if query.data == 'show_stalkers':
        show_stalkers(query, user_id, user_data)
    elif query.data == 'buy_membership':
        show_membership_options(query)
    elif query.data.startswith('membership_'):
        process_membership_selection(query, user_id)
    elif query.data.startswith('payment_'):
        process_payment_method(query, user_id)
    elif query.data == 'referral_info':
        show_referral_info(query, user_id, user_data)
    elif query.data == 'back_to_menu':
        start(update, context)
    elif query.data == 'admin_panel':
        admin_panel(query)
    elif query.data == 'admin_view_payments':
        admin_view_payments(query)
    elif query.data.startswith('admin_approve_'):
        admin_process_payment(query, True)
    elif query.data.startswith('admin_reject_'):
        admin_process_payment(query, False)
    elif query.data == 'admin_manage_payments':
        admin_manage_payment_methods(query)
    elif query.data.startswith('admin_add_payment_'):
        admin_add_payment_method(query)
    elif query.data.startswith('admin_remove_payment_'):
        admin_remove_payment_method(query)
    elif query.data == 'admin_ban_user':
        query.edit_message_text("Lütfen yasaklamak istediğiniz kullanıcının ID'sini girin:")
        context.user_data["admin_action"] = "ban"
    elif query.data == 'admin_unban_user':
        query.edit_message_text("Lütfen yasağını kaldırmak istediğiniz kullanıcının ID'sini girin:")
        context.user_data["admin_action"] = "unban"
    elif query.data == 'admin_change_password':
        query.edit_message_text("Lütfen yeni admin şifresini girin:")
        context.user_data["admin_action"] = "change_password"

def show_stalkers(query, user_id, user_data):
    # Kullanıcının üyeliği var mı kontrol et
    if user_data["membership_end"] and user_data["membership_end"] > datetime.now():
        # Üyeliği varsa
        stalkers = db.get_unused_profiles(user_id, random.randint(1, 5))
        message = "🔍 Bugün seni stalklayanlar:\n\n"
        for stalker in stalkers:
            hidden_username = stalker["username"][:2] + "*" * (len(stalker["username"]) - 2)
            message += f"👤 @{hidden_username}\n"
        
        query.edit_message_text(message)
    else:
        # İlk sorgu ücretsiz
        if not user_data["used_profiles"]:
            stalkers = db.get_unused_profiles(user_id, random.randint(1, 5))
            message = "🎁 İlk sorgun ücretsiz! Bugün seni stalklayanlar:\n\n"
            for stalker in stalkers:
                hidden_username = stalker["username"][:2] + "*" * (len(stalker["username"]) - 2)
                message += f"👤 @{hidden_username}\n"
            
            message += "\n🔒 Daha fazla görmek için üyelik satın almalısın."
            query.edit_message_text(message)
        else:
            query.edit_message_text(
                "⏳ İlk ücretsiz sorgunu zaten kullandın.\n"
                "🔓 Daha fazla görmek için üyelik satın almalısın.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💳 Üyelik Satın Al", callback_data='buy_membership')],
                    [InlineKeyboardButton("🔙 Ana Menü", callback_data='back_to_menu')]
                ])
            )

def show_membership_options(query):
    buttons = []
    for plan, prices in PRICES.items():
        text = f"{plan.capitalize()} - {prices['tl']}₺ ({prices['usd']}$)"
        buttons.append([InlineKeyboardButton(text, callback_data=f'membership_{plan}')])
    
    buttons.append([InlineKeyboardButton("🔙 Ana Menü", callback_data='back_to_menu')])
    
    query.edit_message_text(
        "💎 Üyelik Planları:\n\n"
        "📅 Günlük: 30₺ (1$)\n"
        "📆 Haftalık: 200₺ (6$)\n"
        "📆 Aylık: 500₺ (15$)\n"
        "📅 Yıllık: 1500₺ (45$)\n\n"
        "Lütfen bir plan seçin:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

def process_membership_selection(query, user_id):
    plan = query.data.split('_')[1]
    prices = PRICES.get(plan, {})
    
    buttons = []
    for method in db.payment_methods:
        buttons.append([InlineKeyboardButton(method, callback_data=f'payment_{plan}_{method}')])
    
    buttons.append([InlineKeyboardButton("🔙 Geri", callback_data='buy_membership')])
    
    query.edit_message_text(
        f"💳 Ödeme Yöntemi Seçin ({plan.capitalize()} - {prices['tl']}₺):\n\n"
        "Ödeme yaptıktan sonra dekontu bana gönderin.",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

def process_payment_method(query, user_id):
    _, plan, method = query.data.split('_', 2)
    prices = PRICES.get(plan, {})
    
    query.edit_message_text(
        f"✅ {plan.capitalize()} üyelik için {prices['tl']}₺ ({prices['usd']}$) tutarını "
        f"{method} ile ödeme yapın.\n\n"
        "💾 Ödeme yaptıktan sonra dekont/fatura fotoğrafını bu sohbete gönderin.\n\n"
        "⚠️ Dekontunuzda kullanıcı ID'niz ({user_id}) mutlaka görünür olmalıdır.".format(user_id=user_id)
    )

def show_referral_info(query, user_id, user_data):
    referral_link = f"https://t.me/{context.bot.username}?start={user_id}"
    
    query.edit_message_text(
        "👥 Referans Programı:\n\n"
        f"🔗 Referans linkin: {referral_link}\n\n"
        f"📊 Toplam referans: {user_data['referrals']}\n"
        "🎁 15 referans yapana 1 hafta bedava üyelik!\n\n"
        "Yeni kullanıcılar referans linkinle botu başlattığında otomatik olarak sayılır.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Ana Menü", callback_data='back_to_menu')]
        ])
    )

def handle_receipt(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    user_data = db.get_user(user_id)
    
    if user_data["banned"]:
        update.message.reply_text("⛔ Hesabınız yasaklanmıştır. Admin ile iletişime geçin.")
        return
    
    if update.message.photo:
        receipt = update.message.photo[-1].file_id
    elif update.message.document:
        receipt = update.message.document.file_id
    else:
        update.message.reply_text("Lütfen geçerli bir dekont/fatura gönderin (fotoğraf veya belge).")
        return
    
    # Kullanıcının son seçtiği üyelik planını ve ödeme yöntemini al
    # Bu basit örnekte son işlem olarak saklamadık, gerçek uygulamada context.user_data kullanılmalı
    # Burada varsayılan değerler kullanıyoruz
    plan = "monthly"
    method = "Banka Havalesi"
    
    db.add_payment(user_id, PRICES[plan]["tl"], plan, receipt, method)
    
    update.message.reply_text(
        "✅ Dekontunuz alındı ve admin onayına gönderildi.\n\n"
        "⏳ En geç 24 saat içinde üyeliğiniz aktif edilecektir.\n"
        "📬 Onaylandığında size bildirilecektir."
    )

def admin_login(update: Update, context: CallbackContext):
    if len(context.args) == 2:
        username, password = context.args
        if username == ADMIN_USERNAME and password == db.admin_password:
            context.user_data["admin_logged_in"] = True
            update.message.reply_text("✅ Admin paneline giriş yapıldı.", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛠️ Admin Paneli", callback_data='admin_panel')]
            ]))
        else:
            update.message.reply_text("❌ Hatalı kullanıcı adı veya şifre!")
    else:
        update.message.reply_text("Kullanım: /justadmin <kullanıcıadı> <şifre>")

def admin_panel(query):
    query.edit_message_text(
        "🛠️ Admin Paneli\n\n"
        "Lütfen bir işlem seçin:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Bekleyen Ödemeler", callback_data='admin_view_payments')],
            [InlineKeyboardButton("💳 Ödeme Yöntemleri", callback_data='admin_manage_payments')],
            [InlineKeyboardButton("⛔ Kullanıcı Yasakla", callback_data='admin_ban_user')],
            [InlineKeyboardButton("✅ Kullanıcı Yasağını Kaldır", callback_data='admin_unban_user')],
            [InlineKeyboardButton("🔑 Şifre Değiştir", callback_data='admin_change_password')],
            [InlineKeyboardButton("🔙 Çıkış", callback_data='back_to_menu')]
        ])
    )

def admin_view_payments(query):
    pending_payments = db.get_pending_payments()
    
    if not pending_payments:
        query.edit_message_text("✅ Bekleyen ödeme bulunmamaktadır.")
        return
    
    message = "📝 Bekleyen Ödemeler:\n\n"
    buttons = []
    
    for i, payment in enumerate(pending_payments):
        message += (
            f"{i+1}. Kullanıcı ID: {payment['user_id']}\n"
            f"   Plan: {payment['type'].capitalize()}\n"
            f"   Tutar: {payment['amount']}₺\n"
            f"   Yöntem: {payment['method']}\n\n"
        )
        
        buttons.append([
            InlineKeyboardButton(f"✅ Onayla {i+1}", callback_data=f'admin_approve_{i}'),
            InlineKeyboardButton(f"❌ Reddet {i+1}", callback_data=f'admin_reject_{i}')
        ])
    
    buttons.append([InlineKeyboardButton("🔙 Geri", callback_data='admin_panel')])
    
    query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(buttons))

def admin_process_payment(query, approve):
    payment_index = int(query.data.split('_')[-1])
    
    if approve:
        if db.approve_payment(payment_index):
            query.answer("✅ Ödeme onaylandı!")
        else:
            query.answer("❌ Onaylama başarısız!")
    else:
        if db.reject_payment(payment_index):
            query.answer("❌ Ödeme reddedildi!")
        else:
            query.answer("❌ Reddetme başarısız!")
    
    admin_view_payments(query)

def admin_manage_payment_methods(query):
    buttons = []
    
    # Mevcut ödeme yöntemlerini listele
    for method in db.payment_methods:
        buttons.append([InlineKeyboardButton(f"❌ Kaldır: {method}", callback_data=f'admin_remove_payment_{method}')])
    
    # Yeni ekleme butonları
    buttons.append([InlineKeyboardButton("➕ Banka Havalesi Ekle", callback_data='admin_add_payment_Banka Havalesi')])
    buttons.append([InlineKeyboardButton("➕ Papara Ekle", callback_data='admin_add_payment_Papara')])
    buttons.append([InlineKeyboardButton("➕ Kripto Para Ekle", callback_data='admin_add_payment_Kripto Para')])
    
    buttons.append([InlineKeyboardButton("🔙 Geri", callback_data='admin_panel')])
    
    query.edit_message_text(
        "💳 Ödeme Yöntemleri Yönetimi\n\n"
        "Mevcut yöntemler:\n- " + "\n- ".join(db.payment_methods) + "\n\n"
        "Yeni yöntem eklemek veya mevcutları kaldırmak için butonları kullanın:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

def admin_add_payment_method(query):
    method = query.data.split('_')[-1]
    if db.add_payment_method(method):
        query.answer(f"✅ {method} eklendi!")
    else:
        query.answer(f"⚠️ {method} zaten mevcut!")
    admin_manage_payment_methods(query)

def admin_remove_payment_method(query):
    method = '_'.join(query.data.split('_')[3:])
    if db.remove_payment_method(method):
        query.answer(f"✅ {method} kaldırıldı!")
    else:
        query.answer(f"❌ {method} bulunamadı!")
    admin_manage_payment_methods(query)

def handle_admin_actions(update: Update, context: CallbackContext):
    if not context.user_data.get("admin_logged_in"):
        update.message.reply_text("❌ Yetkisiz erişim!")
        return
    
    action = context.user_data.get("admin_action")
    text = update.message.text
    
    if action == "ban":
        try:
            user_id = int(text)
            user_data = db.get_user(user_id)
            user_data["banned"] = True
            update.message.reply_text(f"✅ Kullanıcı {user_id} yasaklandı!")
        except ValueError:
            update.message.reply_text("❌ Geçersiz kullanıcı ID'si!")
    
    elif action == "unban":
        try:
            user_id = int(text)
            user_data = db.get_user(user_id)
            user_data["banned"] = False
            update.message.reply_text(f"✅ Kullanıcı {user_id} yasağı kaldırıldı!")
        except ValueError:
            update.message.reply_text("❌ Geçersiz kullanıcı ID'si!")
    
    elif action == "change_password":
        db.admin_password = text
        update.message.reply_text("✅ Admin şifresi güncellendi!")
    
    context.user_data["admin_action"] = None

def main():
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher
    
    # Komutlar
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("justadmin", admin_login))
    
    # Butonlar
    dispatcher.add_handler(CallbackQueryHandler(button_handler))
    
    # Mesajlar
    dispatcher.add_handler(MessageHandler(Filters.photo | Filters.document, handle_receipt))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_admin_actions))
    
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
