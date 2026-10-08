// Gate Entry QR Scanner JavaScript
class QRScanner {
    constructor() {
        this.video = document.getElementById('qr-scanner-video');
        this.canvas = document.getElementById('qr-canvas');
        this.ctx = this.canvas.getContext('2d', { willReadFrequently: true });
        this.infoCard = document.getElementById('scanned-info-card');
        this.scanning = false;
        this.lastScan = null;
        this.scanDelay = 2000; // 2 seconds delay between scans
        
        this.initializeCamera();
        this.setupEventListeners();
    }
    
    async initializeCamera() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'environment' }
            });
            this.video.srcObject = stream;
            this.video.addEventListener('loadedmetadata', () => {
                this.video.play();
                this.startScanning();
            });
        } catch (error) {
            console.error('Error accessing camera:', error);
            this.showError('Unable to access camera. Please ensure camera permissions are granted.');
        }
    }
    
    startScanning() {
        this.scanning = true;
        this.scanFrame();
    }
    
    stopScanning() {
        this.scanning = false;
        if (this.video.srcObject) {
            this.video.srcObject.getTracks().forEach(track => track.stop());
        }
    }
    
    scanFrame() {
        if (!this.scanning) return;
        
        if (this.video.readyState === this.video.HAVE_ENOUGH_DATA) {
            this.canvas.width = this.video.videoWidth;
            this.canvas.height = this.video.videoHeight;
            this.ctx.drawImage(this.video, 0, 0);
            
            const imageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
            const code = jsQR(imageData.data, imageData.width, imageData.height);
            
            if (code) {
                this.handleQRCode(code.data);
            }
        }
        
        requestAnimationFrame(() => this.scanFrame());
    }
    
    handleQRCode(data) {
        const now = Date.now();
        if (this.lastScan && now - this.lastScan < this.scanDelay) {
            return; // Too soon since last scan
        }
        
        this.lastScan = now;
        this.processQRData(data);
    }
    
    async processQRData(qrData) {
        try {
            this.showLoading();
            
            // Dispatch scan start event
            window.dispatchEvent(new CustomEvent('qr-scan-start'));
            
            const logType = document.querySelector('input[name="log_type"]:checked')?.value || 'ENTRY';
            
            const response = await fetch('/api/scan_qr', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    qr_data: qrData,
                    log_type: logType
                })
            });
            
            const result = await response.json();
            
            if (response.ok && result.success) {
                this.displayScanResult(result);
                this.playSuccessSound();
            } else {
                this.showError(result.message || 'Failed to process QR code');
                this.playErrorSound();
                // Dispatch error event
                window.dispatchEvent(new CustomEvent('qr-scan-error'));
            }
        } catch (error) {
            console.error('Error processing QR code:', error);
            this.showError('Network error. Please try again.');
            this.playErrorSound();
            // Dispatch error event
            window.dispatchEvent(new CustomEvent('qr-scan-error'));
        }
    }
    
    displayScanResult(data) {
        const card = this.infoCard;
        card.innerHTML = `
            <div class="card-header">
                <h5 class="card-title mb-0">
                    <i class="fas fa-${data.log_type === 'ENTRY' ? 'sign-in-alt text-success' : 'sign-out-alt text-danger'}"></i>
                    Vehicle ${data.log_type === 'ENTRY' ? 'Entry' : 'Exit'} - ${data.timestamp ? new Date(data.timestamp).toLocaleString() : 'N/A'}
                </h5>
            </div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-6">
                        <h6><i class="fas fa-user"></i> Resident Information</h6>
                        <p><strong>Name:</strong> ${data.resident_name}</p>
                        <p><strong>ID:</strong> ${data.resident_id}</p>
                        <p><strong>Email:</strong> ${data.resident_email}</p>
                        <p><strong>Phone:</strong> ${data.resident_phone}</p>
                        <p><strong>Location:</strong> Floor ${data.floor_no}, Door ${data.door_no}</p>
                        <p><strong>Status:</strong> <span class="badge bg-${data.resident_status === 'Current Resident' ? 'success' : 'warning'}">${data.resident_status}</span></p>
                    </div>
                    <div class="col-md-6">
                        <h6><i class="fas fa-car"></i> Vehicle Information</h6>
                        <p><strong>Vehicle No:</strong> ${data.vehicle_no}</p>
                        <p><strong>Company:</strong> ${data.vehicle_company}</p>
                        <p><strong>Type:</strong> ${data.vehicle_type}</p>
                        <p><strong>Model:</strong> ${data.vehicle_model}</p>
                        <p><strong>Color:</strong> ${data.vehicle_color}</p>
                    </div>
                </div>
                <div class="row mt-3">
                    <div class="col-12">
                        <h6><i class="fas fa-parking"></i> Parking Details</h6>
                        <p><strong>Parking Slot:</strong> ${data.parking_slot}</p>
                        <p><strong>Location:</strong> ${data.parking_location}</p>
                        <p><strong>Type:</strong> <span class="badge bg-${data.parking_type && data.parking_type.includes('Resident') ? 'primary' : 'secondary'}">${data.parking_type}</span></p>
                    </div>
                </div>
                <div class="mt-3">
                    <div class="alert alert-${data.log_type === 'ENTRY' ? 'success' : 'info'}" role="alert">
                        <i class="fas fa-${data.log_type === 'ENTRY' ? 'check-circle' : 'info-circle'}"></i>
                        ${data.message}
                    </div>
                </div>
            </div>
        `;
        
        card.classList.remove('d-none');
        card.classList.add('show');
        
        // Dispatch success event
        window.dispatchEvent(new CustomEvent('qr-scan-success'));
        
        // Auto-hide after 10 seconds
        setTimeout(() => {
            this.clearScanResult();
        }, 10000);
    }
    
    clearScanResult() {
        const card = this.infoCard;
        card.classList.remove('show');
        setTimeout(() => {
            card.classList.add('d-none');
            card.innerHTML = '';
        }, 300);
    }
    
    showLoading() {
        const card = this.infoCard;
        card.innerHTML = `
            <div class="card-body text-center">
                <div class="spinner"></div>
                <p>Processing QR Code...</p>
            </div>
        `;
        card.classList.remove('d-none');
    }
    
    showError(message) {
        const card = this.infoCard;
        card.innerHTML = `
            <div class="card-body">
                <div class="alert alert-danger" role="alert">
                    <i class="fas fa-exclamation-triangle"></i>
                    ${message}
                </div>
            </div>
        `;
        card.classList.remove('d-none');
        card.classList.add('show');
        
        // Auto-hide after 5 seconds
        setTimeout(() => {
            this.clearScanResult();
        }, 5000);
    }
    
    playSuccessSound() {
        // Create a simple success sound
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        oscillator.frequency.value = 800;
        oscillator.type = 'sine';
        gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
        
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.5);
    }
    
    playErrorSound() {
        // Create a simple error sound
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        
        oscillator.frequency.value = 300;
        oscillator.type = 'sawtooth';
        gainNode.gain.setValueAtTime(0.2, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);
        
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.3);
    }
    
    setupEventListeners() {
        // Clear scan button
        document.getElementById('clear-scan-btn')?.addEventListener('click', () => {
            this.clearScanResult();
        });
        
        // Log type change
        document.querySelectorAll('input[name="log_type"]').forEach(radio => {
            radio.addEventListener('change', () => {
                this.clearScanResult();
            });
        });
        
        // Stop scanning when page is about to unload
        window.addEventListener('beforeunload', () => {
            this.stopScanning();
        });
    }
}

// Initialize QR Scanner when page loads
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('qr-scanner-video')) {
        new QRScanner();
    }
});
