// 16kHz Mono WAV Recorder using Web Audio API
class WavAudioRecorder {
    constructor() {
        this.audioContext = null;
        this.mediaStream = null;
        this.scriptProcessor = null;
        this.inputPoint = null;
        this.audioBuffers = [];
        this.targetSampleRate = 16000;
        this.isRecording = false;
        this.recordingLength = 0;
    }

    async start() {
        if (this.isRecording) return;
        this.audioBuffers = [];
        this.recordingLength = 0;

        try {
            // Request microphone access
            this.mediaStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });

            // Initialize AudioContext
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const source = this.audioContext.createMediaStreamSource(this.mediaStream);
            
            // Create ScriptProcessor (buffer size 4096, 1 input channel, 1 output channel)
            const bufferSize = 4096;
            this.scriptProcessor = this.audioContext.createScriptProcessor(bufferSize, 1, 1);
            
            source.connect(this.scriptProcessor);
            this.scriptProcessor.connect(this.audioContext.destination);

            const sourceSampleRate = this.audioContext.sampleRate;

            this.scriptProcessor.onaudioprocess = (e) => {
                if (!this.isRecording) return;
                const inputData = e.inputBuffer.getChannelData(0);
                
                // Resample chunk on-the-fly to 16000Hz
                const resampledChunk = this.resample(inputData, sourceSampleRate, this.targetSampleRate);
                this.audioBuffers.push(resampledChunk);
                this.recordingLength += resampledChunk.length;
            };

            this.isRecording = true;
            console.log("Audio recording started...");
        } catch (err) {
            console.error("Failed to start audio recording:", err);
            throw err;
        }
    }

    stop() {
        if (!this.isRecording) return null;
        this.isRecording = false;

        // Disconnect nodes
        if (this.scriptProcessor) {
            this.scriptProcessor.disconnect();
            this.scriptProcessor = null;
        }
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
            this.mediaStream = null;
        }
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }

        console.log("Audio recording stopped. Encoding WAV...");
        return this.encodeWAV();
    }

    resample(inputData, fromSampleRate, toSampleRate) {
        if (fromSampleRate === toSampleRate) return new Float32Array(inputData);
        
        const interpolationRatio = fromSampleRate / toSampleRate;
        const newLength = Math.round(inputData.length / interpolationRatio);
        const result = new Float32Array(newLength);
        
        for (let i = 0; i < newLength; i++) {
            const nearestIndex = Math.min(Math.round(i * interpolationRatio), inputData.length - 1);
            result[i] = inputData[nearestIndex];
        }
        return result;
    }

    encodeWAV() {
        // Flatten buffer array
        const mergedBuffer = new Float32Array(this.recordingLength);
        let offset = 0;
        for (let i = 0; i < this.audioBuffers.length; i++) {
            mergedBuffer.set(this.audioBuffers[i], offset);
            offset += this.audioBuffers[i].length;
        }

        const buffer = new ArrayBuffer(44 + mergedBuffer.length * 2);
        const view = new DataView(buffer);

        /* RIFF identifier */
        this.writeString(view, 0, 'RIFF');
        /* file length */
        view.setUint32(4, 36 + mergedBuffer.length * 2, true);
        /* RIFF type */
        this.writeString(view, 8, 'WAVE');
        /* format chunk identifier */
        this.writeString(view, 12, 'fmt ');
        /* format chunk length */
        view.setUint32(16, 16, true);
        /* sample format (raw PCM) */
        view.setUint16(20, 1, true);
        /* channel count (mono) */
        view.setUint16(22, 1, true);
        /* sample rate */
        view.setUint32(24, this.targetSampleRate, true);
        /* byte rate (sample rate * block align) */
        view.setUint32(28, this.targetSampleRate * 2, true);
        /* block align (channel count * bytes per sample) */
        view.setUint16(32, 2, true);
        /* bits per sample */
        view.setUint16(34, 16, true);
        /* data chunk identifier */
        this.writeString(view, 36, 'data');
        /* data chunk length */
        view.setUint32(40, mergedBuffer.length * 2, true);

        // Float to 16-bit Signed PCM conversion
        let volume = 1.0;
        let index = 44;
        for (let i = 0; i < mergedBuffer.length; i++) {
            let s = Math.max(-1, Math.min(1, mergedBuffer[i] * volume));
            view.setInt16(index, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
            index += 2;
        }

        return new Blob([view], { type: 'audio/wav' });
    }

    writeString(view, offset, string) {
        for (let i = 0; i < string.length; i++) {
            view.setUint8(offset + i, string.charCodeAt(i));
        }
    }
}
