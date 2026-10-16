/**
 * Victoria AI - Audio Waveform & Oscilloscope Visualizer
 * Renders real-time dynamic frequency waves on HTML5 Canvas.
 */

class AudioWaveformVisualizer {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');

        this.isActive = false;
        this.audioContext = null;
        this.analyser = null;
        this.dataArray = null;

        this.phase = 0;
        this.render();
    }

    connectAudioElement(audioElement) {
        try {
            if (!this.audioContext) {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
            const source = this.audioContext.createMediaElementSource(audioElement);
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 128;
            source.connect(this.analyser);
            this.analyser.connect(this.audioContext.destination);

            const bufferLength = this.analyser.frequencyBinCount;
            this.dataArray = new Uint8Array(bufferLength);
            this.isActive = true;
        } catch (e) {
            console.log("Audio visualizer WebAudio notice:", e);
        }
    }

    render() {
        requestAnimationFrame(() => this.render());
        if (!this.ctx || !this.canvas) return;

        const width = this.canvas.width;
        const height = this.canvas.height;
        this.ctx.clearRect(0, 0, width, height);

        this.phase += 0.05;

        if (this.isActive && this.analyser && this.dataArray) {
            this.analyser.getByteFrequencyData(this.dataArray);
            const barWidth = (width / this.dataArray.length) * 1.5;
            let x = 0;

            for (let i = 0; i < this.dataArray.length; i++) {
                const barHeight = (this.dataArray[i] / 255) * height * 0.9;

                const grad = this.ctx.createLinearGradient(0, height, 0, 0);
                grad.addColorStop(0, '#00f0ff');
                grad.addColorStop(1, '#a855f7');

                this.ctx.fillStyle = grad;
                this.ctx.fillRect(x, height - barHeight, barWidth - 1, barHeight);
                x += barWidth;
            }
        } else {
            // Ambient idle flowing sine wave
            this.ctx.beginPath();
            this.ctx.lineWidth = 2;
            this.ctx.strokeStyle = '#00f0ff88';

            for (let x = 0; x < width; x++) {
                const y = height / 2 + Math.sin(x * 0.04 + this.phase) * 8 + Math.cos(x * 0.02 - this.phase * 0.7) * 4;
                if (x === 0) {
                    this.ctx.moveTo(x, y);
                } else {
                    this.ctx.lineTo(x, y);
                }
            }
            this.ctx.stroke();

            // Secondary ghost wave (purple)
            this.ctx.beginPath();
            this.ctx.lineWidth = 1.5;
            this.ctx.strokeStyle = '#a855f755';
            for (let x = 0; x < width; x++) {
                const y = height / 2 + Math.sin(x * 0.03 - this.phase * 1.2) * 6;
                if (x === 0) this.ctx.moveTo(x, y);
                else this.ctx.lineTo(x, y);
            }
            this.ctx.stroke();
        }
    }
}

window.waveformVisualizer = null;
window.addEventListener('DOMContentLoaded', () => {
    window.waveformVisualizer = new AudioWaveformVisualizer('waveformCanvas');
});
