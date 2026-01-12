"""
Multi-Webcam Order Management System with VAD + Whisper
Robotic Arm Order Processing System with Voice Control
"""

import gradio as gr
import whisper
import numpy as np
import webrtcvad
import struct
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
import json
from datetime import datetime

# ==================== 系統全局變數與資料結構 ====================

class SystemState(Enum):
    """系統狀態枚舉"""
    IDLE = "待機中"
    WAIT_CONFIRM = "等待確認"
    FETCHING = "取料中"
    HANDOVER = "交接中"
    WAIT_REFILL = "等待補料"
    ASSEMBLING = "組裝中"


@dataclass
class Order:
    """訂單資料結構"""
    order_id: str
    product_model: str
    custom_requirements: Dict[str, str]  # 顏色、外殼等客製化需求
    bom_list: List[str]  # 物料清單
    status: str = "PENDING"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class SystemContext:
    """系統上下文 - 全局狀態管理"""
    state: SystemState = SystemState.IDLE
    order_queue: List[Order] = field(default_factory=list)
    current_order: Optional[Order] = None
    current_bom_index: int = 0
    missing_list: List[str] = field(default_factory=list)
    inventory: Dict[str, int] = field(default_factory=dict)
    message_log: List[str] = field(default_factory=list)
    
    def log(self, message: str):
        """添加訊息到日誌"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.message_log.append(f"[{timestamp}] {message}")
        # 只保留最近 50 條訊息
        if len(self.message_log) > 50:
            self.message_log = self.message_log[-50:]
    
    def get_log_text(self) -> str:
        """獲取日誌文字"""
        return "\n".join(self.message_log[-20:])  # 顯示最近 20 條


# 初始化系統上下文
ctx = SystemContext()

# 初始化模擬庫存
ctx.inventory = {
    "螺絲A": 10,
    "螺絲B": 5,
    "外殼_藍色": 3,
    "外殼_紅色": 0,  # 模擬缺料
    "主板": 2,
    "電池": 8,
    "傳感器": 0,  # 模擬缺料
    "連接線": 15,
}

# 初始化模擬訂單隊列
ctx.order_queue = [
    Order(
        order_id="ORD-2026-001",
        product_model="RoboArm-X100",
        custom_requirements={"顏色": "藍色", "外殼": "標準"},
        bom_list=["螺絲A", "外殼_藍色", "主板", "電池", "連接線"]
    ),
    Order(
        order_id="ORD-2026-002",
        product_model="RoboArm-X200",
        custom_requirements={"顏色": "紅色", "外殼": "加強"},
        bom_list=["螺絲B", "外殼_紅色", "主板", "傳感器", "電池"]
    ),
]

# ==================== Whisper 與 VAD 初始化 ====================

print("Loading Whisper model...")
whisper_model = whisper.load_model("whisperModel/medium.pt")
print("Whisper model loaded!")

vad = webrtcvad.Vad(3)

HALLUCINATION_PATTERNS = [
    "掰掰", "拜拜", "再見", "謝謝觀看", "謝謝收看", "訂閱", "按讚",
    "感謝收看", "感謝觀看", "下次見", "我們下次見",
    "請訂閱", "喜歡", "分享", "留言",
    "字幕", "翻譯", "CC", "Subtitles",
    "Thanks for watching", "Subscribe", "Like",
    "bye", "goodbye", "see you",
    "...", "。。。", "~~~",
]

# ==================== 核心業務邏輯函數 ====================

def get_status_display():
    """獲取當前狀態顯示"""
    status_lines = [
        f"🔄 系統狀態: {ctx.state.value}",
        f"📦 訂單隊列: {len(ctx.order_queue)} 筆待處理",
    ]
    
    if ctx.current_order:
        status_lines.extend([
            f"📋 當前訂單: {ctx.current_order.order_id}",
            f"�icing 型號: {ctx.current_order.product_model}",
            f"🎨 客製需求: {ctx.current_order.custom_requirements}",
            f"📊 BOM進度: {ctx.current_bom_index}/{len(ctx.current_order.bom_list)}",
        ])
        if ctx.missing_list:
            status_lines.append(f"⚠️ 缺料清單: {ctx.missing_list}")
    
    return "\n".join(status_lines)


# =============== 階段一：系統初始化與訂單啟動 ===============

def cmd_system_start():
    """系統啟動指令"""
    if ctx.state != SystemState.IDLE:
        ctx.log(f"❌ 無法啟動：當前狀態為 {ctx.state.value}")
        return get_status_display(), ctx.get_log_text()
    
    if not ctx.order_queue:
        ctx.log("📭 目前無待處理訂單")
        return get_status_display(), ctx.get_log_text()
    
    # 載入第一筆訂單
    ctx.current_order = ctx.order_queue[0]
    ctx.current_bom_index = 0
    ctx.missing_list = []
    ctx.state = SystemState.WAIT_CONFIRM
    
    ctx.log(f"📢 新訂單通知：{ctx.current_order.order_id}")
    ctx.log(f"   型號：{ctx.current_order.product_model}")
    ctx.log(f"   客製需求：{ctx.current_order.custom_requirements}")
    ctx.log(f"   物料清單：{ctx.current_order.bom_list}")
    ctx.log("⏳ 請確認訂單需求後回覆「OK」")
    
    return get_status_display(), ctx.get_log_text()


def cmd_confirm_order():
    """確認訂單 (OK)"""
    if ctx.state != SystemState.WAIT_CONFIRM:
        ctx.log(f"❌ 無法確認：當前狀態為 {ctx.state.value}")
        return get_status_display(), ctx.get_log_text()
    
    ctx.state = SystemState.FETCHING
    ctx.log("✅ 訂單已確認，開始備料程序")
    
    # 自動開始第一個物料的取料
    return _process_next_item()


def cmd_cancel_order():
    """取消當前訂單"""
    if ctx.state == SystemState.IDLE:
        ctx.log("❌ 無訂單可取消")
        return get_status_display(), ctx.get_log_text()
    
    ctx.log(f"🚫 已取消訂單：{ctx.current_order.order_id if ctx.current_order else 'N/A'}")
    ctx.current_order = None
    ctx.current_bom_index = 0
    ctx.missing_list = []
    ctx.state = SystemState.IDLE
    
    return get_status_display(), ctx.get_log_text()


def cmd_pause_system():
    """暫停系統"""
    prev_state = ctx.state
    ctx.log(f"⏸️ 系統已暫停 (原狀態: {prev_state.value})")
    ctx.state = SystemState.IDLE
    return get_status_display(), ctx.get_log_text()


# =============== 階段二：智慧備料與物料循環 ===============

def _process_next_item():
    """處理下一個 BOM 項目"""
    if not ctx.current_order:
        ctx.log("❌ 無當前訂單")
        return get_status_display(), ctx.get_log_text()
    
    bom = ctx.current_order.bom_list
    
    # 檢查是否已完成所有 BOM 項目
    if ctx.current_bom_index >= len(bom):
        # 進入階段三：檢查缺料
        return _check_missing_items()
    
    target_item = bom[ctx.current_bom_index]
    stock = ctx.inventory.get(target_item, 0)
    
    if stock > 0:
        # 正常取料流程
        ctx.inventory[target_item] -= 1  # 扣除庫存
        ctx.state = SystemState.HANDOVER
        ctx.log(f"🤖 正在拿取：{target_item}")
        ctx.log(f"   庫存剩餘：{ctx.inventory[target_item]}")
        ctx.log(f"   robotic_arm 正在配送物料至工作站...")
        ctx.log("⏳ 請取走物料後說「下一個物件」")
    else:
        # 缺料處理 - 非阻塞式
        ctx.log(f"⚠️ {target_item} 缺料！正在申請補料...")
        ctx.log(f"📤 已發送補料請求至倉儲系統 (WMS)")
        ctx.missing_list.append(target_item)
        ctx.current_bom_index += 1
        # 自動處理下一個項目
        return _process_next_item()
    
    return get_status_display(), ctx.get_log_text()


def cmd_next_item():
    """下一個物件指令"""
    if ctx.state != SystemState.HANDOVER:
        ctx.log(f"❌ 無法執行：當前狀態為 {ctx.state.value}")
        return get_status_display(), ctx.get_log_text()
    
    ctx.log("✅ 物料已取走")
    ctx.current_bom_index += 1
    ctx.state = SystemState.FETCHING
    
    return _process_next_item()


# =============== 階段三：缺料補救與回補循環 ===============

def _check_missing_items():
    """檢查缺料清單"""
    if not ctx.missing_list:
        # 無缺料，進入組裝階段
        ctx.log("✅ 物料拿取完畢！")
        ctx.state = SystemState.ASSEMBLING
        ctx.log("🔧 請進行組裝作業")
        ctx.log("⏳ 組裝完成後請說「OK，下一單」")
    else:
        # 有缺料，進入等待補料
        ctx.state = SystemState.WAIT_REFILL
        ctx.log(f"⏳ 等待補料：{ctx.missing_list}")
        ctx.log("📦 補料完成後請點擊「補料完成」")
        
        # 全缺料死鎖檢測
        if len(ctx.missing_list) == len(ctx.current_order.bom_list):
            ctx.log("🚨 嚴重警報：全部物料缺貨！請求人工介入")
    
    return get_status_display(), ctx.get_log_text()


def cmd_refill_complete():
    """補料完成指令"""
    if ctx.state != SystemState.WAIT_REFILL:
        ctx.log(f"❌ 無法執行：當前狀態為 {ctx.state.value}")
        return get_status_display(), ctx.get_log_text()
    
    ctx.log("📦 收到補料完成信號，重新檢查庫存...")
    
    # 模擬補料 - 實際應用中這裡會重新查詢數據庫
    for item in ctx.missing_list[:]:
        # 模擬補料成功
        ctx.inventory[item] = ctx.inventory.get(item, 0) + 5
        ctx.log(f"   ✅ {item} 已補貨 (庫存: {ctx.inventory[item]})")
    
    # 重新處理缺料清單
    ctx.state = SystemState.FETCHING
    items_to_process = ctx.missing_list.copy()
    ctx.missing_list = []
    
    for item in items_to_process:
        stock = ctx.inventory.get(item, 0)
        if stock > 0:
            ctx.inventory[item] -= 1
            ctx.state = SystemState.HANDOVER
            ctx.log(f"🤖 正在拿取補料項目：{item}")
            ctx.log("⏳ 請取走物料後說「下一個物件」")
            return get_status_display(), ctx.get_log_text()
        else:
            ctx.missing_list.append(item)
    
    # 如果還有缺料
    if ctx.missing_list:
        ctx.state = SystemState.WAIT_REFILL
        ctx.log(f"⚠️ 仍有缺料：{ctx.missing_list}")
    else:
        ctx.log("✅ 所有物料拿取完畢！")
        ctx.state = SystemState.ASSEMBLING
        ctx.log("🔧 請進行組裝作業")
    
    return get_status_display(), ctx.get_log_text()


# =============== 階段四：組裝與結案 ===============

def cmd_complete_order():
    """完成訂單，下一單"""
    if ctx.state != SystemState.ASSEMBLING:
        ctx.log(f"❌ 當前訂單尚未完成，請先完成物料點收")
        ctx.log(f"   當前狀態: {ctx.state.value}")
        return get_status_display(), ctx.get_log_text()
    
    # 結案當前訂單
    completed_order = ctx.current_order
    ctx.log(f"🎉 訂單 {completed_order.order_id} 已完成！")
    
    # 從隊列中移除
    if ctx.order_queue and ctx.order_queue[0].order_id == completed_order.order_id:
        ctx.order_queue.pop(0)
    
    # 清理狀態
    ctx.current_order = None
    ctx.current_bom_index = 0
    ctx.missing_list = []
    
    # 檢查是否還有訂單
    if ctx.order_queue:
        ctx.log(f"📋 載入下一筆訂單...")
        ctx.current_order = ctx.order_queue[0]
        ctx.state = SystemState.WAIT_CONFIRM
        ctx.log(f"📢 新訂單：{ctx.current_order.order_id}")
        ctx.log(f"   型號：{ctx.current_order.product_model}")
        ctx.log(f"   客製需求：{ctx.current_order.custom_requirements}")
        ctx.log("⏳ 請確認後回覆「OK」")
    else:
        ctx.log("📭 目前無更多訂單")
        ctx.state = SystemState.IDLE
    
    return get_status_display(), ctx.get_log_text()


# =============== 輔助功能 ===============

def cmd_check_inventory():
    """查看庫存"""
    ctx.log("📊 當前庫存狀態：")
    for item, qty in ctx.inventory.items():
        status = "✅" if qty > 0 else "❌"
        ctx.log(f"   {status} {item}: {qty}")
    return get_status_display(), ctx.get_log_text()


def cmd_add_test_order():
    """新增測試訂單"""
    new_order = Order(
        order_id=f"ORD-TEST-{len(ctx.order_queue)+1:03d}",
        product_model="TestModel-001",
        custom_requirements={"顏色": "綠色", "外殼": "測試"},
        bom_list=["螺絲A", "電池", "連接線"]
    )
    ctx.order_queue.append(new_order)
    ctx.log(f"➕ 已新增測試訂單：{new_order.order_id}")
    return get_status_display(), ctx.get_log_text()


def cmd_reset_system():
    """重置系統"""
    global ctx
    ctx = SystemContext()
    ctx.inventory = {
        "螺絲A": 10, "螺絲B": 5, "外殼_藍色": 3, "外殼_紅色": 0,
        "主板": 2, "電池": 8, "傳感器": 0, "連接線": 15,
    }
    ctx.order_queue = [
        Order("ORD-2026-001", "RoboArm-X100", {"顏色": "藍色"}, ["螺絲A", "外殼_藍色", "主板", "電池"]),
        Order("ORD-2026-002", "RoboArm-X200", {"顏色": "紅色"}, ["螺絲B", "外殼_紅色", "傳感器"]),
    ]
    ctx.log("🔄 系統已重置")
    return get_status_display(), ctx.get_log_text()


# ==================== VAD 與 Whisper 函數 ====================

def audio_contains_speech(audio_data, sample_rate):
    """使用 WebRTC VAD 檢測語音"""
    try:
        if sample_rate != 16000:
            import torchaudio
            import torch
            audio_tensor = torch.from_numpy(audio_data.astype(np.float32)).unsqueeze(0)
            resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
            audio_data = resampler(audio_tensor).squeeze().numpy()
            sample_rate = 16000
        
        if audio_data.dtype == np.float32 or audio_data.max() <= 1.0:
            audio_16bit = (audio_data * 32767).astype(np.int16)
        else:
            audio_16bit = audio_data.astype(np.int16)
        
        if len(audio_16bit.shape) > 1:
            audio_16bit = audio_16bit.mean(axis=1).astype(np.int16)
        
        frame_duration_ms = 30
        frame_size = int(sample_rate * frame_duration_ms / 1000)
        speech_frames = 0
        total_frames = 0
        
        for i in range(0, len(audio_16bit) - frame_size, frame_size):
            frame = audio_16bit[i:i + frame_size]
            frame_bytes = struct.pack('%dh' % len(frame), *frame)
            try:
                if vad.is_speech(frame_bytes, sample_rate):
                    speech_frames += 1
            except:
                pass
            total_frames += 1
        
        if total_frames > 0:
            return speech_frames / total_frames > 0.2
        return False
    except Exception as e:
        print(f"VAD error: {e}")
        return True


def transcribe_audio(audio_data, sample_rate):
    """使用 Whisper 轉錄音頻"""
    if audio_data is None or len(audio_data) == 0:
        return ""
    
    audio_data = audio_data.astype(np.float32)
    if audio_data.max() > 1.0:
        audio_data = audio_data / 32768.0
    
    if len(audio_data.shape) > 1:
        audio_data = audio_data.mean(axis=1)
    
    if sample_rate != 16000:
        import torchaudio
        import torch
        audio_tensor = torch.from_numpy(audio_data).unsqueeze(0)
        resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
        audio_data = resampler(audio_tensor).squeeze().numpy()
    
    result = whisper_model.transcribe(audio_data, fp16=False, language="zh")
    return result["text"].strip()


def process_audio_stream(audio, history_text):
    """處理音頻流並執行語音指令"""
    if audio is None:
        return history_text or "", "🔇 等待語音輸入..."
    
    sample_rate, audio_data = audio
    
    if len(audio_data) < sample_rate * 0.5:
        return history_text or "", "🔇 等待語音輸入..."
    
    has_speech = audio_contains_speech(audio_data, sample_rate)
    
    if not has_speech:
        return history_text or "", "🔇 沒有偵測到語音"
    
    transcribed = transcribe_audio(audio_data, sample_rate)
    
    if not transcribed:
        return history_text or "", "🎤 偵測到語音，正在處理..."
    
    transcribed_clean = transcribed.strip()
    for pattern in HALLUCINATION_PATTERNS:
        if pattern.lower() in transcribed_clean.lower():
            return history_text or "", f"🔇 過濾: {transcribed_clean}"
    
    if len(transcribed_clean) <= 2:
        return history_text or "", "🔇 輸出太短"
    
    current = history_text or ""
    if current:
        current += "\n"
    current += f"🎤 {transcribed_clean}"
    
    if len(current) > 800:
        current = current[-800:]
    
    return current, f"✅ 辨識: {transcribed_clean[:30]}..."


# ==================== Gradio 介面 ====================

def create_interface():
    """建立 Gradio 介面"""
    
    with gr.Blocks(title="機械手臂訂單管理系統") as demo:
        gr.Markdown("# 🤖 機械手臂訂單管理系統")
        gr.Markdown("*結合語音控制的智慧製造流程管理*")
        
        # ===== 上半部：3 個攝影機 =====
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 📷 Camera 1")
                gr.Image(sources=["webcam"], streaming=True, label="Camera 1")
            with gr.Column(scale=1):
                gr.Markdown("### 📷 Camera 2")
                gr.Image(sources=["webcam"], streaming=True, label="Camera 2")
            with gr.Column(scale=1):
                gr.Markdown("### 📷 Camera 3")
                gr.Image(sources=["webcam"], streaming=True, label="Camera 3")
        
        # ===== 下半部：控制面板 =====
        with gr.Row():
            # 左側：系統狀態與回應
            with gr.Column(scale=1):
                gr.Markdown("### 🤖 系統狀態與回應")
                
                status_display = gr.Textbox(
                    label="系統狀態",
                    lines=6,
                    interactive=False,
                    value=get_status_display(),
                )
                
                system_log = gr.Textbox(
                    label="系統訊息日誌",
                    lines=12,
                    interactive=False,
                    value="系統就緒，等待啟動...",
                )
                
                # ===== 按鈕組 1：系統控制 =====
                gr.Markdown("#### 🔧 系統控制")
                with gr.Row():
                    btn_start = gr.Button("🚀 系統啟動", variant="primary")
                    btn_pause = gr.Button("⏸️ 暫停", variant="secondary")
                    btn_reset = gr.Button("🔄 重置系統", variant="secondary")
                
                # ===== 按鈕組 2：訂單確認 =====
                gr.Markdown("#### 📋 訂單確認 (階段一)")
                with gr.Row():
                    btn_confirm = gr.Button("✅ OK 確認訂單", variant="primary")
                    btn_cancel = gr.Button("❌ 取消訂單", variant="stop")
                
                # ===== 按鈕組 3：取料控制 =====
                gr.Markdown("#### 📦 取料控制 (階段二)")
                with gr.Row():
                    btn_next = gr.Button("➡️ 下一個物件", variant="primary")
                
                # ===== 按鈕組 4：補料處理 =====
                gr.Markdown("#### 🔄 補料處理 (階段三)")
                with gr.Row():
                    btn_refill = gr.Button("📦 補料完成", variant="primary")
                
                # ===== 按鈕組 5：結案 =====
                gr.Markdown("#### ✅ 結案 (階段四)")
                with gr.Row():
                    btn_complete = gr.Button("🎉 OK，下一單", variant="primary")
                
                # ===== 按鈕組 6：輔助功能 =====
                gr.Markdown("#### 🛠️ 輔助功能")
                with gr.Row():
                    btn_inventory = gr.Button("📊 查看庫存")
                    btn_add_order = gr.Button("➕ 新增測試訂單")
            
            # 右側：語音輸入
            with gr.Column(scale=1):
                gr.Markdown("### 🎤 語音輸入 (VAD + Whisper)")
                
                vad_status = gr.Textbox(
                    label="VAD 狀態",
                    value="🔇 等待語音輸入...",
                    interactive=False,
                )
                
                audio_input = gr.Audio(
                    sources=["microphone"],
                    streaming=True,
                    label="🎙️ 麥克風 (持續監聽)",
                )
                
                transcript_display = gr.Textbox(
                    label="語音辨識結果",
                    lines=8,
                    interactive=False,
                    placeholder="開始說話... VAD 會偵測語音後進行辨識",
                )
                
                audio_input.stream(
                    fn=process_audio_stream,
                    inputs=[audio_input, transcript_display],
                    outputs=[transcript_display, vad_status],
                )
                
                btn_clear_voice = gr.Button("🗑️ 清除語音記錄")
                btn_clear_voice.click(
                    fn=lambda: ("", "🔇 等待語音輸入..."),
                    outputs=[transcript_display, vad_status],
                )
        
        # ===== 綁定按鈕事件 =====
        btn_start.click(cmd_system_start, outputs=[status_display, system_log])
        btn_pause.click(cmd_pause_system, outputs=[status_display, system_log])
        btn_reset.click(cmd_reset_system, outputs=[status_display, system_log])
        btn_confirm.click(cmd_confirm_order, outputs=[status_display, system_log])
        btn_cancel.click(cmd_cancel_order, outputs=[status_display, system_log])
        btn_next.click(cmd_next_item, outputs=[status_display, system_log])
        btn_refill.click(cmd_refill_complete, outputs=[status_display, system_log])
        btn_complete.click(cmd_complete_order, outputs=[status_display, system_log])
        btn_inventory.click(cmd_check_inventory, outputs=[status_display, system_log])
        btn_add_order.click(cmd_add_test_order, outputs=[status_display, system_log])
    
    return demo


if __name__ == "__main__":
    demo = create_interface()
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=True,
        show_error=True,
        theme=gr.themes.Soft(primary_hue="blue", secondary_hue="slate"),
    )
