"""
Remote Control Interface for Robotic Arm Order Management System
遠端控制介面 - 透過 API 控制主應用程式
"""

import gradio as gr
import requests
from typing import Tuple

# API 設定
API_BASE = "http://localhost:1872"


def call_api(endpoint: str) -> Tuple[str, str]:
    """呼叫主應用 API，只回傳狀態和日誌"""
    try:
        response = requests.post(f"{API_BASE}/api/{endpoint}", timeout=5)
        response.raise_for_status()
        data = response.json()
        return data.get("status", ""), data.get("log", "")
    except requests.exceptions.ConnectionError:
        return "❌ 連線失敗：無法連接到主應用程式", "請確認 webcam_app.py 已啟動"
    except requests.exceptions.Timeout:
        return "❌ 連線逾時", "API 回應超時"
    except Exception as e:
        return f"❌ 錯誤: {e}", ""


def fetch_status() -> Tuple[str, str]:
    """取得當前狀態"""
    try:
        response = requests.get(f"{API_BASE}/api/status", timeout=5)
        response.raise_for_status()
        data = response.json()
        return data.get("status", ""), data.get("log", "")
    except:
        return "無法連接到主應用程式", "請確認 webcam_app.py 已啟動於 port 1870"


# ==================== 按鈕事件處理函數 ====================

def btn_start_click():
    return call_api("start")

def btn_pause_click():
    return call_api("pause")

def btn_reset_click():
    return call_api("reset")

def btn_confirm_click():
    return call_api("confirm")

def btn_cancel_click():
    return call_api("cancel")

def btn_next_click():
    return call_api("next")

def btn_refill_click():
    return call_api("refill")

def btn_complete_click():
    return call_api("complete")

def btn_inventory_click():
    return call_api("inventory")

def btn_add_order_click():
    return call_api("add_order")


# ==================== Gradio 介面 ====================

def create_remote_interface():
    """建立遠端控制介面"""
    
    with gr.Blocks(title="遠端控制台 - 機械手臂") as demo:
        gr.Markdown("# 🎮 遠端控制台")
        gr.Markdown("*透過 API 控制機械手臂訂單管理系統*")
        
        with gr.Row():
            # 左側：狀態顯示
            with gr.Column(scale=1):
                gr.Markdown("### 🤖 系統狀態")
                status_display = gr.Textbox(label="系統狀態", lines=6, interactive=False, value="等待連接...")
                system_log = gr.Textbox(label="系統訊息日誌", lines=12, interactive=False, value="嘗試連接主應用程式...")
            
            # 右側：控制按鈕
            with gr.Column(scale=1):
                gr.Markdown("### 🔧 系統控制")
                with gr.Row():
                    btn_start = gr.Button("🚀 系統啟動", variant="primary")
                    btn_pause = gr.Button("⏸️ 暫停", variant="secondary")
                    btn_reset = gr.Button("🔄 重置系統", variant="secondary")
                
                gr.Markdown("### 📋 訂單確認")
                with gr.Row():
                    btn_confirm = gr.Button("✅ OK 確認訂單", variant="primary")
                    btn_cancel = gr.Button("❌ 取消訂單", variant="stop")
                
                gr.Markdown("### 📦 取料控制")
                with gr.Row():
                    btn_next = gr.Button("➡️ 下一個物件", variant="primary")
                
                gr.Markdown("### 🔄 補料處理")
                with gr.Row():
                    btn_refill = gr.Button("📦 補料完成", variant="primary")
                
                gr.Markdown("### ✅ 結案")
                with gr.Row():
                    btn_complete = gr.Button("🎉 開始組裝", variant="primary")
                
                gr.Markdown("### 🛠️ 輔助功能")
                with gr.Row():
                    btn_inventory = gr.Button("📊 查看庫存")
                    btn_add_order = gr.Button("➕ 新增測試訂單")
        
        # 綁定按鈕事件
        outputs = [status_display, system_log]
        
        btn_start.click(btn_start_click, outputs=outputs)
        btn_pause.click(btn_pause_click, outputs=outputs)
        btn_reset.click(btn_reset_click, outputs=outputs)
        btn_confirm.click(btn_confirm_click, outputs=outputs)
        btn_cancel.click(btn_cancel_click, outputs=outputs)
        btn_next.click(btn_next_click, outputs=outputs)
        btn_refill.click(btn_refill_click, outputs=outputs)
        btn_complete.click(btn_complete_click, outputs=outputs)
        btn_inventory.click(btn_inventory_click, outputs=outputs)
        btn_add_order.click(btn_add_order_click, outputs=outputs)
        
        # 自動刷新狀態
        timer = gr.Timer(1.0)  # 每秒刷新一次
        timer.tick(fn=fetch_status, outputs=[status_display, system_log])
    
    return demo


if __name__ == "__main__":
    print("🎮 遠端控制台啟動中...")
    print("📡 API 目標: http://localhost:1872")
    print("🌐 請確認主應用程式 (webcam_app.py) 已經啟動")
    
    demo = create_remote_interface()
    demo.launch(
        server_name="0.0.0.0",
        server_port=1871,
        share=True,  # 啟用公開分享，產生手機可用的網址
        show_error=True,
        theme=gr.themes.Soft(primary_hue="green", secondary_hue="slate"),
    )
