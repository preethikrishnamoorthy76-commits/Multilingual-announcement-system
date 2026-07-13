let authToken = localStorage.getItem('access_token');

if (!authToken) {
    window.location.href = '/';
}

// Initialize profile page
document.addEventListener('DOMContentLoaded', function() {
    loadUserProfile();
    checkTelegramStatus();
    loadUserPreferences();
    initializeTabNavigation();
});

// Initialize tab navigation
function initializeTabNavigation() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const targetTab = this.getAttribute('data-tab');
            
            // Remove active class from all tabs and contents
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            
            // Add active class to clicked tab and corresponding content
            this.classList.add('active');
            document.getElementById(`${targetTab}-tab`).classList.add('active');
        });
    });
}

// Logout function
document.getElementById('logoutBtn').addEventListener('click', function() {
    localStorage.removeItem('access_token');
    window.location.href = '/';
});

// Load user profile information
async function loadUserProfile() {
    try {
        // Get username from localStorage or API
        const username = localStorage.getItem('username') || 'User';
        
        // Since Account Settings tab is hidden, we don't need to populate those fields
        // Just keep this function for future use
        updateProfileStats();
    } catch (error) {
        console.error('Error loading user profile:', error);
    }
}

// Update profile statistics (demo data)
function updateProfileStats() {
    // This function is no longer needed since we removed the profile header
    // but keeping it for backward compatibility
    return;
}

// Load user preferences
async function loadUserPreferences() {
    try {
        const response = await fetch('/api/user/preferences', {
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            const preferences = await response.json();
            document.getElementById('preferredLanguage').value = preferences.preferred_language || 'en';
            document.getElementById('audioNotifications').checked = preferences.audio_notifications || false;
        } else {
            console.error('Failed to load preferences from database');
            // Fallback to localStorage for backward compatibility
            const savedLanguage = localStorage.getItem('preferredLanguage') || 'en';
            const audioEnabled = localStorage.getItem('audioNotifications') === 'true';
            
            document.getElementById('preferredLanguage').value = savedLanguage;
            document.getElementById('audioNotifications').checked = audioEnabled;
        }
    } catch (error) {
        console.error('Error loading preferences:', error);
        // Fallback to localStorage
        const savedLanguage = localStorage.getItem('preferredLanguage') || 'en';
        const audioEnabled = localStorage.getItem('audioNotifications') === 'true';
        
        document.getElementById('preferredLanguage').value = savedLanguage;
        document.getElementById('audioNotifications').checked = audioEnabled;
    }
}

// Save user preferences
document.getElementById('savePreferencesBtn').addEventListener('click', async function() {
    try {
        const preferredLanguage = document.getElementById('preferredLanguage').value;
        const audioNotifications = document.getElementById('audioNotifications').checked;
        
        const response = await fetch('/api/user/preferences', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                preferred_language: preferredLanguage,
                audio_notifications: audioNotifications
            })
        });

        if (response.ok) {
            const result = await response.json();
            
            // Also save to localStorage for backward compatibility
            localStorage.setItem('preferredLanguage', preferredLanguage);
            localStorage.setItem('audioNotifications', audioNotifications.toString());
            
            showAlert('Preferences saved successfully!', 'success');
        } else {
            const errorData = await response.json();
            showAlert(errorData.detail || 'Failed to save preferences', 'error');
        }
    } catch (error) {
        console.error('Error saving preferences:', error);
        showAlert('Error saving preferences', 'error');
    }
});

// TELEGRAM INTEGRATION FUNCTIONS

let verificationPollingInterval = null;

// Check Telegram status
async function checkTelegramStatus() {
    try {
        const response = await fetch('/api/telegram/status', {
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            const data = await response.json();
            updateTelegramUI(data.linked, data.chat_id, data.verified, data.has_pending_verification);
        } else {
            console.error('Failed to check Telegram status');
            updateTelegramUI(false, null, false, false);
        }
    } catch (error) {
        console.error('Error checking Telegram status:', error);
        showAlert('Error checking Telegram status', 'error');
        updateTelegramUI(false, null, false, false);
    }
}

function updateTelegramUI(isLinked, chatId, isVerified, hasPendingVerification) {
    const statusIndicator = document.querySelector('.status-indicator');
    const statusText = document.querySelector('.telegram-status span');
    const connectedChatIdDiv = document.getElementById('connectedChatId');

    // ALWAYS hide all sections first to ensure only one is visible
    hideAllTelegramSections();

    if (isLinked && isVerified) {
        // STEP 3 ONLY: Successfully connected - show ONLY connected section
        statusIndicator.className = 'status-indicator status-connected';
        statusText.textContent = 'Connected and Verified';
        showTelegramSection('connectedSection');
        connectedChatIdDiv.textContent = chatId || 'Not available';
        
        // Stop polling if verification is complete
        if (verificationPollingInterval) {
            clearInterval(verificationPollingInterval);
            verificationPollingInterval = null;
        }
    } else if (hasPendingVerification) {
        // STEP 2 ONLY: Token generated, waiting for verification - show ONLY token section
        statusIndicator.className = 'status-indicator status-pending';
        statusText.textContent = 'Verification Pending';
        showTelegramSection('tokenGeneratedSection');
        
        // Update the generated token display
        updateGeneratedTokenDisplay();
        startVerificationPolling();
    } else {
        // STEP 1 ONLY: Initial state, need to generate token - show ONLY initial instructions
        statusIndicator.className = 'status-indicator status-disconnected';
        statusText.textContent = 'Not connected to Telegram';
        showTelegramSection('initialInstructions');
        
        // Stop any existing polling
        if (verificationPollingInterval) {
            clearInterval(verificationPollingInterval);
            verificationPollingInterval = null;
        }
    }
}

// Helper function to ensure all telegram sections are hidden
function hideAllTelegramSections() {
    const sections = [
        'initialInstructions',
        'tokenGeneratedSection', 
        'connectedSection'
    ];
    
    sections.forEach(sectionId => {
        const section = document.getElementById(sectionId);
        if (section) {
            section.style.display = 'none';
            section.classList.add('hidden');
        }
    });
}

function showTelegramSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (section) {
        section.style.display = 'block';
        section.classList.remove('hidden');
    }
}

function updateGeneratedTokenDisplay() {
    fetch('/api/telegram/pending-token', {
        headers: {
            'Authorization': `Bearer ${authToken}`,
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.token) {
            const token = data.token;
            const generatedTokenElement = document.getElementById('generatedToken');
            const telegramDirectLink = document.getElementById('telegramDirectLink');
            
            // Update token display
            generatedTokenElement.textContent = token;
            
            // Update direct link
            const botUsername = 'Multilingotrain_bot'; // Replace with your actual bot username
            const telegramUrl = `https://t.me/${botUsername}?text=${encodeURIComponent(token)}`;
            telegramDirectLink.href = telegramUrl;
            
            // Generate and display QR code
            generateAndDisplayQRCode();
        }
    })
    .catch(error => {
        console.error('Error fetching pending token:', error);
    });
}

async function generateAndDisplayQRCode() {
    try {
        const response = await fetch('/api/telegram/qr-code', {
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            const data = await response.json();
            const qrDisplay = document.getElementById('qrCodeDisplay');
            const downloadBtn = document.querySelector('.qr-download-btn');
            
            // Create QR code image element
            const qrImg = document.createElement('img');
            qrImg.src = data.qr_code_base64;
            qrImg.alt = 'Telegram Verification QR Code';
            qrImg.style.display = 'block';
            
            // Clear loading spinner and add QR code
            qrDisplay.innerHTML = '';
            qrDisplay.appendChild(qrImg);
            
            // Show download button and set up download functionality
            if (downloadBtn) {
                downloadBtn.style.display = 'inline-block';
                downloadBtn.onclick = () => downloadQRCode(data.qr_code_base64, `telegram_verification_qr.png`);
            }
        } else {
            const errorData = await response.json();
            console.error('Error generating QR code:', errorData);
            const qrDisplay = document.getElementById('qrCodeDisplay');
            qrDisplay.innerHTML = '<div class="loading-spinner">Failed to generate QR code</div>';
        }
    } catch (error) {
        console.error('Error generating QR code:', error);
        const qrDisplay = document.getElementById('qrCodeDisplay');
        qrDisplay.innerHTML = '<div class="loading-spinner">Error generating QR code</div>';
    }
}

async function generateToken() {
    try {
        const response = await fetch('/api/telegram/generate-token', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            const data = await response.json();
            showAlert('Verification token generated successfully!', 'success');
            
            // EXPLICIT STEP TRANSITION: Hide all sections, Show Step 2 ONLY
            hideAllTelegramSections();
            showTelegramSection('tokenGeneratedSection');
            
            // Reset QR code display to loading state
            const qrDisplay = document.getElementById('qrCodeDisplay');
            const downloadBtn = document.querySelector('.qr-download-btn');
            qrDisplay.innerHTML = '<div class="loading-spinner">Loading QR Code...</div>';
            if (downloadBtn) {
                downloadBtn.style.display = 'none';
            }
            
            // Update the status to reflect token generation
            const statusIndicator = document.querySelector('.status-indicator');
            const statusText = document.querySelector('.telegram-status span');
            statusIndicator.className = 'status-indicator status-pending';
            statusText.textContent = 'Token Generated - Awaiting Verification';
            
            // Update token display and start polling
            updateGeneratedTokenDisplay();
            startVerificationPolling();
        } else {
            const errorData = await response.json();
            showAlert(errorData.error || 'Failed to generate verification token', 'error');
        }
    } catch (error) {
        console.error('Error generating token:', error);
        showAlert('Error generating verification token', 'error');
    }
}

function startVerificationPolling() {
    // Poll every 3 seconds to check if verification is complete
    if (verificationPollingInterval) {
        clearInterval(verificationPollingInterval);
    }
    
    verificationPollingInterval = setInterval(async () => {
        try {
            await checkTelegramStatus();
        } catch (error) {
            console.error('Error during verification polling:', error);
        }
    }, 3000);
    
    // Stop polling after 5 minutes
    setTimeout(() => {
        if (verificationPollingInterval) {
            clearInterval(verificationPollingInterval);
            verificationPollingInterval = null;
            showAlert('Verification polling stopped. Please generate a new token if needed.', 'info');
        }
    }, 300000);
}

function copyToken() {
    const tokenText = document.getElementById('generatedToken').textContent;
    navigator.clipboard.writeText(tokenText).then(() => {
        showAlert('Token copied to clipboard!', 'success');
    }).catch(() => {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = tokenText;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        showAlert('Token copied to clipboard!', 'success');
    });
}

function downloadQRCode(base64Data, filename) {
    try {
        // Create a temporary anchor element for download
        const link = document.createElement('a');
        link.href = base64Data;
        link.download = filename || 'telegram_qr_code.png';
        
        // Trigger download
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        showAlert('QR code downloaded successfully!', 'success');
    } catch (error) {
        console.error('Error downloading QR code:', error);
        showAlert('Failed to download QR code', 'error');
    }
}

async function unlinkTelegram() {
    if (!confirm('Are you sure you want to unlink your Telegram account?')) {
        return;
    }

    try {
        const response = await fetch('/api/telegram/unlink', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            }
        });

        if (response.ok) {
            showAlert('Telegram account unlinked successfully!', 'success');
            
            // EXPLICIT STEP TRANSITION: Go back to Step 1 ONLY
            hideAllTelegramSections();
            showTelegramSection('initialInstructions');
            
            // Reset QR code display
            const qrDisplay = document.getElementById('qrCodeDisplay');
            const downloadBtn = document.querySelector('.qr-download-btn');
            if (qrDisplay) {
                qrDisplay.innerHTML = '<div class="loading-spinner">Loading QR Code...</div>';
            }
            if (downloadBtn) {
                downloadBtn.style.display = 'none';
            }
            
            // Update status to disconnected
            const statusIndicator = document.querySelector('.status-indicator');
            const statusText = document.querySelector('.telegram-status span');
            statusIndicator.className = 'status-indicator status-disconnected';
            statusText.textContent = 'Not connected to Telegram';
            
            // Stop any polling
            if (verificationPollingInterval) {
                clearInterval(verificationPollingInterval);
                verificationPollingInterval = null;
            }
        } else {
            const errorData = await response.json();
            showAlert(errorData.error || 'Failed to unlink Telegram account', 'error');
        }
    } catch (error) {
        console.error('Error unlinking Telegram:', error);
        showAlert('Error unlinking Telegram account', 'error');
    }
}

async function sendTestMessage() {
    const messageInput = document.getElementById('testMessage');
    const message = messageInput ? messageInput.value.trim() : '';
    
    if (!message) {
        showAlert('Please enter a message', 'error');
        return;
    }

    try {
        const response = await fetch('/api/telegram/send-message', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: message })
        });

        if (response.ok) {
            showAlert('Test message sent successfully!', 'success');
            // Clear the input after successful send
            if (messageInput) {
                messageInput.value = 'Hello from MultiLingo! 🎤';
            }
        } else {
            const errorData = await response.json();
            showAlert(errorData.error || 'Failed to send test message', 'error');
        }
    } catch (error) {
        console.error('Error sending test message:', error);
        showAlert('Error sending test message', 'error');
    }
}

function showAlert(message, type) {
    const alertContainer = document.getElementById('alertContainer');
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.textContent = message;
    
    alertContainer.innerHTML = '';
    alertContainer.appendChild(alertDiv);
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

// Show message in the main message container
function showMessage(message, type = 'info') {
    const messageContainer = document.getElementById('messageContainer');
    const messageDiv = document.createElement('div');
    messageDiv.className = `alert alert-${type}`;
    messageDiv.textContent = message;
    
    messageContainer.innerHTML = '';
    messageContainer.appendChild(messageDiv);
    
    // Auto-hide after 3 seconds
    setTimeout(() => {
        if (messageDiv.parentNode) {
            messageDiv.remove();
        }
    }, 3000);
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (verificationPollingInterval) {
        clearInterval(verificationPollingInterval);
    }
});
