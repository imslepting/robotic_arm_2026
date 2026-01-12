"""
Multi-Webcam Viewer with Chat - Gradio
Displays three webcam feeds in a 2x2 grid with a chatbox.
"""

import gradio as gr


def chat_response(message, history):
    """Handle chat messages. Customize this function for your chatbot logic."""
    # Simple echo response - replace with your own logic
    return f"You said: {message}"


def create_interface():
    """Create 2x2 grid: 3 cameras + 1 chatbox."""
    
    with gr.Blocks(title="Multi-Webcam + Chat") as demo:
        gr.Markdown("# 🎥 Multi-Webcam Viewer with Chat")
        
        # Top row: Camera 1 and Camera 2
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 📷 Camera 1")
                gr.Image(
                    sources=["webcam"],
                    streaming=True,
                    label="Camera 1",
                )
            
            with gr.Column(scale=1):
                gr.Markdown("### 📷 Camera 2")
                gr.Image(
                    sources=["webcam"],
                    streaming=True,
                    label="Camera 2",
                )
        
        # Bottom row: Camera 3 and Chatbox
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 📷 Camera 3")
                gr.Image(
                    sources=["webcam"],
                    streaming=True,
                    label="Camera 3",
                )
            
            with gr.Column(scale=1):
                gr.Markdown("### 💬 Chat")
                gr.ChatInterface(
                    fn=chat_response,
                )
    
    return demo


if __name__ == "__main__":
    demo = create_interface()
    
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=True,
        show_error=True,
        theme=gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="slate",
        ),
    )
