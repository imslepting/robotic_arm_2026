"""
Multi-Webcam Order Management System with Browser TTS
Robotic Arm Order Processing System with Voice Feedback
"""

import gradio as gr
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
from datetime import datetime
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ==================== FastAPI 設定 ====================
api = FastAPI(title="Robotic Arm Control API")
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

output_dir = "data1.txt"
action_count = 0
action_list = ["a1", "a2", "a3", "a4", "a5","b1","b2","b3","b4","b5","error","error","error"]
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
    custom_requirements: Dict[str, str]
    bom_list: List[str]
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
    tts_queue: List[str] = field(default_factory=list)  # TTS 訊息隊列
    last_tts_for_display: str = ""  # 給顯示端的 TTS 訊息
    
    def log(self, message: str):
        """添加訊息到日誌"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.message_log.append(f"[{timestamp}] {message}")
        if len(self.message_log) > 50:
            self.message_log = self.message_log[-50:]
    
    def get_log_text(self) -> str:
        """獲取日誌文字"""
        return "\n".join(self.message_log[-10:])
    
    def speak(self, text: str):
        """添加 TTS 訊息"""
        self.tts_queue.append(text)
    
    def get_tts_text(self) -> str:
        """獲取並清空 TTS 隊列 (供 API 使用)"""
        if self.tts_queue:
            text = " ".join(self.tts_queue)
            self.tts_queue = []
            # 同時儲存給顯示端
            self.last_tts_for_display = text
            return text
        return ""
    
    def get_display_tts(self) -> str:
        """給顯示端 Timer 用的 TTS (取後清空)"""
        text = self.last_tts_for_display
        self.last_tts_for_display = ""
        return text


# 初始化系統上下文
ctx = SystemContext()

# 初始資料定義（供初始化和重置使用）
def get_initial_inventory():
    """取得初始庫存"""
    return {
        "底板": 10, "鏡頭": 5, "白色下蓋": 3, "黑色下蓋": 3,
        "白色上蓋": 1, "黑色上蓋": 3, 
    }

def get_initial_orders():
    """取得初始訂單隊列"""
    return [
        Order("ORD-2026-001", "鏡頭模組-X100", {"顏色": "全白"},
              ["底板", "鏡頭", "白色下蓋", "白色上蓋"]),
        Order("ORD-2026-002", "鏡頭模組-X200", {"顏色": "白上黑下"},
              ["底板", "鏡頭", "白色上蓋", "黑色下蓋"]),
    ]

# 初始化模擬庫存和訂單
ctx.inventory = get_initial_inventory()
ctx.order_queue = get_initial_orders()


# ==================== 核心業務邏輯函數 ====================
def write_action():
    global action_count 
    with open(output_dir, "w") as f:
        f.write(action_list[action_count])
        print(action_list[action_count])
    action_count += 1

def get_status_display():
    """獲取當前狀態顯示"""
    status_lines = [
        f"🔄 系統狀態: {ctx.state.value}",
        f"📦 訂單隊列: {len(ctx.order_queue)} 筆待處理",
    ]
    if ctx.current_order:
        status_lines.extend([
            f"📋 當前訂單: {ctx.current_order.order_id}",
            f"🎨 客製需求: {ctx.current_order.custom_requirements}",
            # f"📊 BOM進度: {ctx.current_bom_index}/{len(ctx.current_order.bom_list)}",
        ])
        if ctx.missing_list:
            status_lines.append(f"⚠️ 缺料清單: {ctx.missing_list}")
    return "\n".join(status_lines)


# =============== 階段一：系統初始化與訂單啟動 ===============

def cmd_system_start():
    """系統啟動指令"""
    if ctx.state != SystemState.IDLE:
        ctx.log(f"❌ 無法啟動：當前狀態為 {ctx.state.value}")
        return get_status_display(), ctx.get_log_text(), ctx.get_tts_text()
    
    if not ctx.order_queue:
        ctx.log("📭 目前無待處理訂單")
        ctx.speak("目前無待處理訂單")
        return get_status_display(), ctx.get_log_text(), ctx.get_tts_text()
    
    ctx.current_order = ctx.order_queue[0]
    ctx.current_bom_index = 0
    ctx.missing_list = []
    ctx.state = SystemState.WAIT_CONFIRM
    
    ctx.log(f"📢 新訂單通知：{ctx.current_order.order_id}")
    ctx.log(f"   型號：{ctx.current_order.product_model}")
    ctx.log(f"   客製需求：{ctx.current_order.custom_requirements}")
    ctx.log(f"   物料清單：{ctx.current_order.bom_list}")
    ctx.log("⏳ 請確認訂單需求後回覆「OK」")
    
    # TTS
    req_text = "，".join([f"{k}{v}" for k, v in ctx.current_order.custom_requirements.items()])
    ctx.speak(f"系統啟動成功。新訂單 {ctx.current_order.product_model}，客製需求：{req_text}")
    
    return get_status_display(), ctx.get_log_text(), ctx.get_tts_text()


def cmd_confirm_order():
    """確認訂單 (OK)"""
    if ctx.state != SystemState.WAIT_CONFIRM:
        ctx.log(f"❌ 無法確認：當前狀態為 {ctx.state.value}")
        return get_status_display(), ctx.get_log_text(), ctx.get_tts_text()
    
    ctx.state = SystemState.FETCHING
    ctx.log("✅ 訂單已確認，開始備料程序")
    return _process_next_item()


def cmd_cancel_order():
    """取消當前訂單"""
    if ctx.state == SystemState.IDLE:
        ctx.log("❌ 無訂單可取消")
        return get_status_display(), ctx.get_log_text(), ctx.get_tts_text()
    
    ctx.log(f"🚫 已取消訂單：{ctx.current_order.order_id if ctx.current_order else 'N/A'}")
    ctx.speak("訂單已取消")
    ctx.current_order = None
    ctx.current_bom_index = 0
    ctx.missing_list = []
    ctx.state = SystemState.IDLE
    
    return get_status_display(), ctx.get_log_text(), ctx.get_tts_text()


def cmd_pause_system():
    """暫停系統"""
    prev_state = ctx.state
    ctx.log(f"⏸️ 系統已暫停 (原狀態: {prev_state.value})")
    ctx.speak("系統暫停")
    ctx.state = SystemState.IDLE
    return get_status_display(), ctx.get_log_text(), ctx.get_tts_text()


# =============== 階段二：智慧備料與物料循環 ===============

def _process_next_item():
    """處理下一個 BOM 項目"""
    if not ctx.current_order:
        ctx.log("❌ 無當前訂單")
        return get_status_display(), ctx.get_log_text(), ctx.get_tts_text()
    
    bom = ctx.current_order.bom_list
    
    if ctx.current_bom_index >= len(bom):
        return _check_missing_items()
    
    target_item = bom[ctx.current_bom_index]
    stock = ctx.inventory.get(target_item, 0)
    
    if stock > 0:
        ctx.inventory[target_item] -= 1
        ctx.state = SystemState.HANDOVER
        ctx.log(f"🤖 正在拿取：{target_item}")
        write_action()
        ctx.log(f"   庫存剩餘：{ctx.inventory[target_item]}")
        
        # 預測下一個是否為空
        is_last_item = (ctx.current_bom_index == len(bom) - 1)
        if is_last_item:
            # 最後一個物件：自動完成物料拿取，直接進入組裝階段
            ctx.current_bom_index += 1  # 更新索引
            ctx.log("✅ 物料拿取完畢！")
            ctx.state = SystemState.ASSEMBLING
            ctx.log("🔧 請進行組裝作業")
            ctx.speak(f"正在拿取{target_item}。物料拿取完畢後，請進行組裝")  # TTS: 提示完成
        else:
            ctx.log("⏳ 請取走物料後說「下一個物件」")
            ctx.speak(f"正在拿取{target_item}")  # TTS: 物料名稱
    else:
        # 缺料：記錄缺料項目，自動跳到下一個物件
        ctx.log(f"⚠️ {target_item} 缺料！需要補貨後才能繼續")
        if target_item not in ctx.missing_list:
            ctx.missing_list.append(target_item)
        write_action()
        
        # 檢查是否還有下一個物件
        next_index = ctx.current_bom_index + 1
        if next_index < len(bom):
            next_item = bom[next_index]
            ctx.log(f"🔄 先拿取 {next_item}")
            ctx.speak(f"{target_item} 缺料，先拿取 {next_item}")
            
            # 跳到下一個物件
            ctx.current_bom_index = next_index
            next_stock = ctx.inventory.get(next_item, 0)
            
            if next_stock > 0:
                ctx.inventory[next_item] -= 1
                ctx.state = SystemState.HANDOVER
                ctx.log(f"🤖 正在拿取：{next_item}")
                ctx.log(f"   庫存剩餘：{ctx.inventory[next_item]}")
                ctx.log("⏳ 請取走物料後說「下一個物件」")
            else:
                # 下一個也缺料
                ctx.log(f"⚠️ {next_item} 也缺料！")
                if next_item not in ctx.missing_list:
                    ctx.missing_list.append(next_item)
                ctx.state = SystemState.WAIT_REFILL
                ctx.log("📦 補料完成後請點擊「補料完成」")
        else:
            # 沒有下一個物件了
            ctx.state = SystemState.WAIT_REFILL
            ctx.speak(f"{target_item} 缺料，請補貨")
            ctx.log(f"🛑 等待補貨：{target_item}")
            ctx.log("📦 補料完成後請點擊「補料完成」")
    
    return get_status_display(), ctx.get_log_text(), ctx.get_tts_text()

def after_refill():
    """處理下一個 BOM 項目"""
    if not ctx.current_order:
        ctx.log("❌ 無當前訂單")
        return get_status_display(), ctx.get_log_text(), ctx.get_tts_text()
    
    bom = ctx.current_order.bom_list
    
    if ctx.current_bom_index >= len(bom):
        return _check_missing_items()
    
    target_item = bom[ctx.current_bom_index]
    stock = ctx.inventory.get(target_item, 0)
    
    if stock > 0:
    #     ctx.inventory[target_item] -= 1
        ctx.state = SystemState.HANDOVER
    #     ctx.log(f"🤖 正在拿取：{target_item}")
    #     ctx.log(f"   庫存剩餘：{ctx.inventory[target_item]}")
    #     ctx.log("⏳ 請取走物料後說「下一個物件」")
    #     ctx.speak(target_item)  # TTS: 物料名稱
    # else:
    #     # 缺料：停留在等待補貨狀態，不跳過
    #     ctx.log(f"⚠️ {target_item} 缺料！需要補貨後才能繼續")
    #     if target_item not in ctx.missing_list:
    #         ctx.missing_list.append(target_item)
    #     ctx.state = SystemState.WAIT_REFILL
    #     ctx.speak(f"{target_item} 缺料，請補貨")  # TTS: 通知缺料
    #     ctx.log(f"🛑 等待補貨：{target_item}")
    #     ctx.log("先取下一個物件")
    #     ctx.log("📦 補料完成後請點擊「補料完成」")
    
    return get_status_display(), ctx.get_log_text(), ctx.get_tts_text()

def cmd_next_item():
    """下一個物件指令"""
    if ctx.state != SystemState.HANDOVER:
        ctx.log(f"❌ 無法執行：當前狀態為 {ctx.state.value}")
        return get_status_display(), ctx.get_log_text(), ctx.get_tts_text()
    
    ctx.log("✅ 物料已取走")
    ctx.current_bom_index += 1
    
    # 檢查是否有缺料需要處理
    if ctx.missing_list:
        bom = ctx.current_order.bom_list
        # 如果 BOM 已經處理完畢，拿取缺料物件
        if ctx.current_bom_index >= len(bom):
            return _process_missing_items()
    
    ctx.state = SystemState.FETCHING
    return _process_next_item()


# =============== 階段三：缺料補救與回補循環 ===============

def _process_missing_items():
    """處理缺料物件 - 拿取缺料清單中的物件"""
    if not ctx.missing_list:
        # 沒有缺料，直接完成
        return _check_missing_items()
    
    # 取第一個缺料物件
    target_item = ctx.missing_list[0]
    stock = ctx.inventory.get(target_item, 0)
    
    if stock > 0:
        ctx.inventory[target_item] -= 1
        ctx.missing_list.pop(0)  # 從缺料清單移除
        ctx.state = SystemState.HANDOVER
        ctx.log(f"🤖 正在拿取：{target_item}（補料）")
        write_action()
        ctx.log(f"   庫存剩餘：{ctx.inventory[target_item]}")
        
        # 檢查是否還有更多缺料
        if ctx.missing_list:
            ctx.log("⏳ 請取走物料後說「下一個物件」")
            ctx.speak(f"正在拿取{target_item}")
        else:
            # 這是最後一個缺料物件，自動完成
            ctx.log("✅ 所有物料拿取完畢！")
            ctx.state = SystemState.ASSEMBLING
            ctx.log("🔧 請進行組裝作業")
            ctx.speak(f"正在拿取{target_item}。物料拿取完畢後，請進行組裝")
    else:
        # 還是缺料，需要等待補貨
        ctx.state = SystemState.WAIT_REFILL
        ctx.speak(f"{target_item} 缺料，請補貨")
        ctx.log(f"🛑 等待補貨：{target_item}")
        ctx.log("📦 補料完成後請點擊「補料完成」")
    
    return get_status_display(), ctx.get_log_text(), ctx.get_tts_text()


def _check_missing_items():
    """檢查缺料清單 - BOM處理完畢時呼叫"""
    # 由於缺料時已經在 _process_next_item 中停住，這裡只處理全部完成的情況
    ctx.log("✅ 物料拿取完畢！")
    write_action()
    ctx.state = SystemState.ASSEMBLING
    ctx.log("🔧 請進行組裝作業")
    ctx.speak("物料拿取完畢，請進行組裝")
    
    return get_status_display(), ctx.get_log_text(), ctx.get_tts_text()


def cmd_refill_complete():
    """補料完成指令"""
    # 允許在 WAIT_REFILL 狀態，或 HANDOVER 狀態且有缺料時執行
    if ctx.state == SystemState.WAIT_REFILL:
        pass  # 正常補料流程
    elif ctx.state == SystemState.HANDOVER and ctx.missing_list:
        pass  # 交接中但有缺料，允許補料
    else:
        ctx.log(f"❌ 無法執行：當前狀態為 {ctx.state.value}")
        return get_status_display(), ctx.get_log_text(), ctx.get_tts_text()
    
    ctx.log("📦 收到補料完成信號，重新檢查庫存...")
    ctx.speak("已補料")
    
    # 補充缺料項目的庫存
    for item in ctx.missing_list:
        ctx.inventory[item] = ctx.inventory.get(item, 0) + 5
        ctx.log(f"   ✅ {item} 已補貨 (庫存: {ctx.inventory[item]})")
    
    # 切換狀態到 HANDOVER，讓使用者可以點擊「下一個物件」
    ctx.state = SystemState.HANDOVER
    ctx.log("⏳ 請點擊「下一個物件」繼續拿取")

    return get_status_display(), ctx.get_log_text(), ctx.get_tts_text()
    # return 0


# =============== 階段四：組裝與結案 ===============

def cmd_complete_order():
    """完成訂單，下一單"""
    if ctx.state != SystemState.ASSEMBLING:
        ctx.log(f"❌ 當前訂單尚未完成")
        return get_status_display(), ctx.get_log_text(), ctx.get_tts_text()
    
    completed_order = ctx.current_order
    ctx.log(f"🎉 訂單 {completed_order.order_id} 已完成！")
    # ctx.speak("載入下一筆訂單")
    write_action()
    
    if ctx.order_queue and ctx.order_queue[0].order_id == completed_order.order_id:
        ctx.order_queue.pop(0)
    
    ctx.current_order = None
    ctx.current_bom_index = 0
    ctx.missing_list = []
    
    if ctx.order_queue:
        ctx.log("📋 載入下一筆訂單...")
        ctx.current_order = ctx.order_queue[0]
        ctx.state = SystemState.WAIT_CONFIRM
        ctx.log(f"📢 新訂單：{ctx.current_order.order_id}")
        req_text = "，".join([f"{k}{v}" for k, v in ctx.current_order.custom_requirements.items()])
        ctx.speak(f"新訂單載入中 {ctx.current_order.product_model}，{req_text}")
    else:
        ctx.log("📭 目前無更多訂單")
        global action_count
        action_count = 0
        ctx.state = SystemState.IDLE
        ctx.speak("無更多訂單")
    
    return get_status_display(), ctx.get_log_text(), ctx.get_tts_text()


# =============== 輔助功能 ===============

def cmd_check_inventory():
    """查看庫存"""
    ctx.log("📊 當前庫存狀態：")
    for item, qty in ctx.inventory.items():
        status = "✅" if qty > 0 else "❌"
        ctx.log(f"   {status} {item}: {qty}")
    return get_status_display(), ctx.get_log_text(), ctx.get_tts_text()


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
    ctx.speak("已新增測試訂單")
    return get_status_display(), ctx.get_log_text(), ctx.get_tts_text()


def cmd_reset_system():
    """重置系統"""
    global ctx
    ctx = SystemContext()
    ctx.inventory = get_initial_inventory()
    ctx.order_queue = get_initial_orders()
    ctx.log("🔄 系統已重置")
    ctx.speak("系統已重置")
    global action_count
    action_count = 0
    return get_status_display(), ctx.get_log_text(), ctx.get_tts_text()


# 語音合成函數 (JavaScript)
def speak_js(text):
    """返回調用 TTS 的 JavaScript"""
    if text:
        return f'speechSynthesis.speak(new SpeechSynthesisUtterance("{text}"))'
    return ""


# ==================== API 端點 ====================

@api.get("/api/status")
def api_get_status():
    """取得當前狀態"""
    return {
        "status": get_status_display(),
        "log": ctx.get_log_text(),
        "tts": ""
    }

@api.post("/api/start")
def api_start():
    """系統啟動"""
    status, log, tts = cmd_system_start()
    return {"status": status, "log": log, "tts": tts}

@api.post("/api/confirm")
def api_confirm():
    """確認訂單"""
    status, log, tts = cmd_confirm_order()
    return {"status": status, "log": log, "tts": tts}

@api.post("/api/cancel")
def api_cancel():
    """取消訂單"""
    status, log, tts = cmd_cancel_order()
    return {"status": status, "log": log, "tts": tts}

@api.post("/api/pause")
def api_pause():
    """暫停系統"""
    status, log, tts = cmd_pause_system()
    return {"status": status, "log": log, "tts": tts}

@api.post("/api/next")
def api_next():
    """下一個物件"""
    status, log, tts = cmd_next_item()
    return {"status": status, "log": log, "tts": tts}

@api.post("/api/refill")
def api_refill():
    """補料完成"""
    status, log, tts = cmd_refill_complete()
    return {"status": status, "log": log, "tts": tts}

@api.post("/api/complete")
def api_complete():
    """完成訂單"""
    status, log, tts = cmd_complete_order()
    return {"status": status, "log": log, "tts": tts}

@api.post("/api/inventory")
def api_inventory():
    """查看庫存"""
    status, log, tts = cmd_check_inventory()
    return {"status": status, "log": log, "tts": tts}

@api.post("/api/add_order")
def api_add_order():
    """新增測試訂單"""
    status, log, tts = cmd_add_test_order()
    return {"status": status, "log": log, "tts": tts}

@api.post("/api/reset")
def api_reset():
    """重置系統"""
    status, log, tts = cmd_reset_system()
    return {"status": status, "log": log, "tts": tts}


# ==================== Gradio 介面 ====================

def create_interface():
    """建立 Gradio 介面"""
    
    with gr.Blocks(title="機械手臂訂單管理系統") as demo:
        gr.Markdown("# 🤖 機械手臂訂單管理系統")
        gr.Markdown("*智慧製造流程管理 | 語音回饋系統*")
        
        # TTS 嵌入式 HTML + JavaScript
        gr.HTML("""
        <script>
        function speakText(text) {
            if (text && text.trim() && 'speechSynthesis' in window) {
                const utterance = new SpeechSynthesisUtterance(text.trim());
                utterance.lang = 'zh-TW';
                utterance.rate = 1.0;
                speechSynthesis.cancel(); // 取消之前的語音
                speechSynthesis.speak(utterance);
                console.log('TTS:', text);
            }
        }
        
        // 監聽 TTS 文字框變化
        setInterval(() => {
            const ttsBox = document.querySelector('#tts_output textarea');
            if (ttsBox && ttsBox.value && ttsBox.value.trim()) {
                speakText(ttsBox.value);
                ttsBox.value = '';
            }
        }, 500);
        
        console.log('TTS 系統已啟動');
        </script>
        <div id="tts_status" style="display:none;">TTS Ready</div>
        """)
        
        # TTS 輸出 (用 CSS 隱藏，確保 textarea 元素存在供 JavaScript 使用)
        gr.HTML('<style>#tts_output { display: none !important; }</style>')
        tts_output = gr.Textbox(elem_id="tts_output", label="TTS", lines=1, interactive=False)
        
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
        
        # ===== 下半部：狀態監控面板 =====
        # 自訂樣式：放大字體
        gr.HTML("""
        <style>
            #status_display textarea, #system_log textarea {
                font-size: 18px !important;
                line-height: 1.5 !important;
            }
            #status_display label, #system_log label {
                font-size: 16px !important;
                font-weight: bold !important;
            }
        </style>
        """)
        
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 🤖 系統狀態")
                status_display = gr.Textbox(
                    elem_id="status_display",
                    label="系統狀態", 
                    lines=10, 
                    interactive=False, 
                    value=get_status_display()
                )
            
            with gr.Column(scale=1):
                gr.Markdown("### 📋 系統訊息日誌")
                system_log = gr.Textbox(
                    elem_id="system_log",
                    label="系統訊息日誌", 
                    lines=10, 
                    interactive=False, 
                    value="系統就緒，等待遠端控制..."
                )
        
        # 自動刷新狀態和 TTS
        def refresh_status():
            return get_status_display(), ctx.get_log_text(), ctx.get_display_tts()
        
        # TTS JavaScript - 在 timer.tick 時執行
        tts_js = """
        (status, log, tts_text) => {
            if (tts_text && tts_text.trim() && 'speechSynthesis' in window) {
                const utterance = new SpeechSynthesisUtterance(tts_text.trim());
                utterance.lang = 'zh-TW';
                utterance.rate = 1.0;
                speechSynthesis.cancel();
                speechSynthesis.speak(utterance);
                console.log('TTS 播放:', tts_text);
            }
            return [status, log, tts_text];
        }
        """
        
        timer = gr.Timer(1.0)  # 每秒刷新一次
        timer.tick(fn=refresh_status, outputs=[status_display, system_log, tts_output]).then(
            fn=None, inputs=[status_display, system_log, tts_output], outputs=[status_display, system_log, tts_output], js=tts_js
        )
    
    return demo


if __name__ == "__main__":
    # 在背景執行 FastAPI
    def run_api():
        uvicorn.run(api, host="0.0.0.0", port=1872, log_level="info")
    
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    print("🚀 API 伺服器已啟動於 http://0.0.0.0:1872")
    
    # 啟動 Gradio
    demo = create_interface()
    demo.launch(
        server_name="0.0.0.0",
        server_port=1870,
        share=False,
        show_error=True,
        theme=gr.themes.Soft(primary_hue="blue", secondary_hue="slate"),
    )

