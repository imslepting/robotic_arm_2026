"""
TTS 語音合成模組
Text-to-Speech Module for Order Management System
"""

import os
import tempfile
import threading
from gtts import gTTS
import pygame

# 初始化 pygame mixer
pygame.mixer.init()

# TTS 配置
TTS_LANGUAGE = "zh-TW"  # 繁體中文
TTS_ENABLED = True  # TTS 開關


def speak(text: str, blocking: bool = False):
    """
    使用 TTS 朗讀文字
    
    Args:
        text: 要朗讀的文字
        blocking: 是否阻塞等待播放完成
    """
    if not TTS_ENABLED or not text:
        return
    
    def _speak():
        try:
            # 創建臨時音頻文件
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
                temp_path = f.name
            
            # 使用 gTTS 生成語音
            tts = gTTS(text=text, lang=TTS_LANGUAGE)
            tts.save(temp_path)
            
            # 播放音頻
            pygame.mixer.music.load(temp_path)
            pygame.mixer.music.play()
            
            # 等待播放完成
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            
            # 清理臨時文件
            try:
                os.remove(temp_path)
            except:
                pass
                
        except Exception as e:
            print(f"TTS Error: {e}")
    
    if blocking:
        _speak()
    else:
        # 非阻塞模式，使用線程
        thread = threading.Thread(target=_speak, daemon=True)
        thread.start()


def speak_system_start():
    """系統啟動語音"""
    speak("系統啟動成功")


def speak_new_order(order_id: str, model: str, requirements: dict):
    """新訂單通知語音"""
    req_text = "，".join([f"{k}{v}" for k, v in requirements.items()])
    speak(f"新訂單 {model}，客製需求：{req_text}")


def speak_material(material_name: str):
    """物料名稱語音"""
    speak(f"正在拿取 {material_name}")


def speak_waiting_refill(missing_items: list):
    """等待補料語音"""
    items_text = "、".join(missing_items)
    speak(f"等待補料 {items_text} 中")


def speak_refill_complete():
    """補料完成語音"""
    speak("已補料")


def speak_order_complete(order_id: str):
    """訂單完成語音"""
    speak(f"訂單完成")


def speak_all_materials_done():
    """物料拿取完畢語音"""
    speak("物料拿取完畢，請進行組裝")


def speak_no_orders():
    """無訂單語音"""
    speak("目前無待處理訂單")


def speak_custom(text: str):
    """自定義語音"""
    speak(text)
