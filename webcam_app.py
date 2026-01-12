"""
Multi-Webcam Viewer with Real-time Speech Detection - Gradio
Displays three webcam feeds with continuous Whisper transcription.
"""

import gradio as gr
import whisper
import numpy as np

# Load Whisper model from local directory
print("Loading Whisper model...")
whisper_model = whisper.load_model("whisperModel/large-v3.pt")
print("Whisper model loaded!")


def transcribe_audio(audio_data, sample_rate):
    """Transcribe audio using Whisper model."""
    if audio_data is None or len(audio_data) == 0:
        return ""
    
    # Convert to float32 and normalize
    audio_data = audio_data.astype(np.float32)
    if audio_data.max() > 1.0:
        audio_data = audio_data / 32768.0
    
    # If stereo, convert to mono
    if len(audio_data.shape) > 1:
        audio_data = audio_data.mean(axis=1)
    
    # Resample to 16kHz if needed
    if sample_rate != 16000:
        import torchaudio
        import torch
        audio_tensor = torch.from_numpy(audio_data).unsqueeze(0)
        resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)
        audio_data = resampler(audio_tensor).squeeze().numpy()
    
    # Transcribe with Whisper (Chinese language)
    result = whisper_model.transcribe(audio_data, fp16=False, language="zh")
    return result["text"].strip()


def process_audio_stream(audio, history_text):
    """Process streaming audio and display transcription."""
    if audio is None:
        return history_text or ""
    
    sample_rate, audio_data = audio
    
    # Skip if too short
    if len(audio_data) < sample_rate * 0.5:  # Less than 0.5 second
        return history_text or ""
    
    # Transcribe
    transcribed = transcribe_audio(audio_data, sample_rate)
    
    if not transcribed:
        return history_text or ""
    
    # Append to history
    current = history_text or ""
    if current:
        current += "\n"
    current += f"🎤 {transcribed}"
    
    # Keep only last 500 characters
    if len(current) > 500:
        current = current[-500:]
    
    return current


def create_interface():
    """Create 2x2 grid: 3 cameras + 1 real-time speech display."""
    
    with gr.Blocks(title="Multi-Webcam + Real-time Speech") as demo:
        gr.Markdown("# 🎥 Multi-Webcam with Real-time Speech Detection")
        
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
        
        # Bottom row: Camera 3 and Speech Detection
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 📷 Camera 3")
                gr.Image(
                    sources=["webcam"],
                    streaming=True,
                    label="Camera 3",
                )
            
            with gr.Column(scale=1):
                gr.Markdown("### 🎤 Real-time Speech Detection")
                
                # Streaming audio input
                audio_input = gr.Audio(
                    sources=["microphone"],
                    streaming=True,
                    label="🎙️ Microphone (Continuous Listening)",
                )
                
                # Real-time transcription display
                transcript_display = gr.Textbox(
                    label="Detected Speech",
                    lines=8,
                    max_lines=10,
                    interactive=False,
                    placeholder="Start speaking... Whisper will transcribe in real-time",
                )
                
                # Process audio stream continuously
                audio_input.stream(
                    fn=process_audio_stream,
                    inputs=[audio_input, transcript_display],
                    outputs=[transcript_display],
                )
                
                # Clear button
                clear_btn = gr.Button("🗑️ Clear")
                clear_btn.click(
                    fn=lambda: "",
                    outputs=[transcript_display],
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
