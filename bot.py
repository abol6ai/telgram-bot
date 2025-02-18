from telegram import Update, InputFile, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from pydub import AudioSegment
import os

# حالة المحادثة
CHOOSING, ADD_COVER, WAITING_FOR_AUDIO, WAITING_FOR_COVER = range(4)

# دالة لتحويل الوقت من دقيقة:ثانية إلى ميلي ثانية
def time_to_ms(time_str):
    minutes, seconds = map(int, time_str.split(":"))
    return (minutes * 60 + seconds) * 1000

# دالة لقص الأغنية باستخدام التنسيق دقيقة:ثانية
def cut_audio(file_path, start_time_str, end_time_str):
    # تحويل الوقت المدخل إلى ميلي ثانية
    start_ms = time_to_ms(start_time_str)
    end_ms = time_to_ms(end_time_str)
    
    audio = AudioSegment.from_file(file_path)
    cut_audio = audio[start_ms:end_ms]
    cut_audio.export("cut_audio.mp3", format="mp3")
    return "cut_audio.mp3"

# دالة لإضافة غلاف للأغنية
def add_cover_to_audio(audio_file, cover_image):
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, APIC

    audio = MP3(audio_file, ID3=ID3)
    with open(cover_image, 'rb') as img:
        audio.tags.add(APIC(
            encoding=3, 
            mime='image/jpeg', 
            type=3, 
            desc='Cover', 
            data=img.read()
        ))
    audio.save()

# دالة لتسمية الأغنية والألبوم
def tag_audio(file_path, song_name, album_name):
    from mutagen.id3 import ID3, TIT2, TALB

    audio = MP3(file_path, ID3=ID3)
    audio.tags.add(TIT2(encoding=3, text=song_name))  # اسم الأغنية
    audio.tags.add(TALB(encoding=3, text=album_name))  # اسم الألبوم
    audio.save()

# بدء المحادثة
def start(update: Update, context: CallbackContext):
    reply_keyboard = [
        [KeyboardButton("نعم، أريد إضافة غلاف"), KeyboardButton("لا، دون غلاف")]
    ]
    update.message.reply_text(
        "مرحبًا! هل ترغب في إضافة غلاف للأغنية؟",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    return CHOOSING

# اختيار إضافة غلاف أو لا
def choose_cover(update: Update, context: CallbackContext):
    user_choice = update.message.text

    if user_choice == "نعم، أريد إضافة غلاف":
        update.message.reply_text("من فضلك، أرسل صورة الغلاف (JPEG أو PNG).")
        return WAITING_FOR_COVER
    else:
        update.message.reply_text("حسنًا! سيتم إرسال الأغنية دون غلاف.")
        return WAITING_FOR_AUDIO

# استقبال الأغنية الصوتية
def receive_audio(update: Update, context: CallbackContext):
    if update.message.audio:
        audio_file = update.message.audio.get_file()
        audio_file.download('song.mp3')
        update.message.reply_text("تم تحميل الأغنية!")

        # طلب وقت البداية والنهاية
        update.message.reply_text("من فضلك، أدخل وقت البداية والنهاية بالتنسيق (دقيقة:ثانية) مثل 1:30 إلى 3:00")
        return WAITING_FOR_AUDIO

# استقبال وقت البداية والنهاية
def receive_time(update: Update, context: CallbackContext):
    times = update.message.text.split(" إلى ")
    if len(times) == 2:
        start_time_str, end_time_str = times
        try:
            # قص الأغنية باستخدام الوقت المحدد
            cut_audio_file = cut_audio('song.mp3', start_time_str, end_time_str)

            # إضافة غلاف إذا اختار المستخدم
            if context.user_data.get("cover_image"):
                add_cover_to_audio(cut_audio_file, context.user_data["cover_image"])

            # تسمية الأغنية والألبوم
            tag_audio(cut_audio_file, "Song Name", "Album Name")

            # إرسال الأغنية المعدلة
            with open(cut_audio_file, 'rb') as f:
                update.message.reply_audio(f)

            return ConversationHandler.END

        except Exception as e:
            update.message.reply_text(f"حدث خطأ: {e}. تأكد من إدخال الوقت بشكل صحيح.")
            return WAITING_FOR_AUDIO
    else:
        update.message.reply_text("التنسيق غير صحيح. تأكد من استخدام الشكل (دقيقة:ثانية) إلى (دقيقة:ثانية). مثل 1:30 إلى 3:00")
        return WAITING_FOR_AUDIO

# استقبال غلاف الصورة
def receive_cover(update: Update, context: CallbackContext):
    if update.message.photo:
        cover_file = update.message.photo[-1].get_file()
        cover_file.download('cover.jpg')
        context.user_data["cover_image"] = 'cover.jpg'
        update.message.reply_text("تم تحميل الغلاف! الآن أرسل الأغنية.")

        return WAITING_FOR_AUDIO

# إنهاء المحادثة
def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("تم إلغاء العملية.")
    return ConversationHandler.END

def main():
    # استبدل "YOUR_TOKEN" بالتوكن الخاص بك
    updater = Updater("8041851526:AAFASVPf-RdWx-pJTf3Ob-dUECkWnIsxVwI", use_context=True)

    # إضافة المعالجين
    dp = updater.dispatcher

    conversation_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING: [MessageHandler(Filters.text & ~Filters.command, choose_cover)],
            WAITING_FOR_COVER: [MessageHandler(Filters.photo, receive_cover)],
            WAITING_FOR_AUDIO: [MessageHandler(Filters.audio, receive_audio), MessageHandler(Filters.text & ~Filters.command, receive_time)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    dp.add_handler(conversation_handler)

    # بدء البوت
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()