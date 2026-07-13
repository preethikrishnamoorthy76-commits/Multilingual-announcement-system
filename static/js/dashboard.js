// Dashboard JavaScript

// Global variables
let supportedLanguages = {};
let currentUser = null;
let selectedLanguage = null;
let isInitializing = false;
let autoRefresh = null;
let availableTrains = [];
let trainStatusCache = {};
let trainStats = {
    total: 0,
    onTime: 0,
    delayed: 0,
    cancelled: 0
};
let userSubscriptions = [];

// API Configuration - can be overridden by setting `window.TRAIN_API_BASE` in a template
const TRAIN_API_BASE = window.TRAIN_API_BASE || '/api';

// DOM Elements
const logoutBtn = document.getElementById('logoutBtn');
const targetLanguagesSelect = document.getElementById('targetLanguages');
const audioSection = document.getElementById('audioSection');
const audioPlayer = document.getElementById('audioPlayer');
const audioLanguage = document.getElementById('audioLanguage');
const audioText = document.getElementById('audioText');
const downloadBtn = document.getElementById('downloadBtn');
const newAudioBtn = document.getElementById('newAudioBtn');
const messageContainer = document.getElementById('messageContainer');
const trainListContainer = document.getElementById('trainListContainer');
const subscriptionsContainer = document.getElementById('subscriptionsContainer');

// Check authentication
let authToken = localStorage.getItem('access_token');
if (!authToken) {
    window.location.href = '/';
}

function bindIfExists(element, eventName, handler) {
    if (element) {
        element.addEventListener(eventName, handler);
    }
}

// Event Listeners
document.addEventListener('DOMContentLoaded', initDashboard);
bindIfExists(logoutBtn, 'click', handleLogout);
bindIfExists(newAudioBtn, 'click', showNewAudioForm);

// Add event listeners for announcement buttons
document.addEventListener('click', function(e) {
    if (e.target.matches('.announcement-btn')) {
        const announcementText = e.target.getAttribute('data-text');
        const announcementCard = e.target.closest('.announcement-card');
        handleTrainAnnouncement(announcementText, announcementCard);
    }
});

// Add event listener for language selection
document.addEventListener('change', function(e) {
    if (e.target.id === 'targetLanguages') {
        const selectedValue = e.target.value;
        if (selectedValue) {
            selectedLanguage = selectedValue;
            localStorage.setItem('selectedLanguage', selectedValue);
            showMessage(`Language set to ${getLanguageName(selectedValue)}`, 'success');
        }
    }
});

// Authentication helper
function getAuthHeaders() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        return null; // Don't redirect here, let the caller handle it
    }
    return {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
    };
}

// Initialization
// Initialize Dashboard
async function initDashboard() {
    try {
        isInitializing = true;
        
        // Load user info
        const username = localStorage.getItem('username') || 'Station Master';
        document.title = `Dashboard - ${username}`;
        
        // Load supported languages
        await loadSupportedLanguages();
        
        // Load saved language preference
        const savedLanguage = localStorage.getItem('selectedLanguage');
        if (savedLanguage && targetLanguagesSelect) {
            targetLanguagesSelect.value = savedLanguage;
            selectedLanguage = savedLanguage;
        }
        
        // Initialize train data
        await initTrainDashboard();
        
        isInitializing = false;
        showMessage('Dashboard loaded successfully!', 'success');
    } catch (error) {
        console.error('Error initializing dashboard:', error);
        showMessage('Error loading dashboard', 'error');
        isInitializing = false;
    }
}

// TRAIN API FUNCTIONS

async function trainApiCall(endpoint, method = 'GET', data = null) {
    try {
        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            }
        };
        
        if (data) {
            options.body = JSON.stringify(data);
        }
        
        const response = await fetch(`${TRAIN_API_BASE}${endpoint}`, options);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error(`API call failed for ${endpoint}:`, error);
        return null;
    }
}

async function initTrainDashboard() {
    try {
        // Hide loading spinner initially
        const loadingSpinner = document.getElementById('loadingSpinner');
        if (loadingSpinner) {
            loadingSpinner.style.display = 'flex';
        }
        
        // Fetch available trains
        await fetchAvailableTrains();
        
        // Render both table and card views
        renderTrainTable();
        renderTrainCards();
        
        // Fetch initial status for all trains
        await loadTrainStatus();
        
        // Hide loading spinner
        if (loadingSpinner) {
            loadingSpinner.style.display = 'none';
        }
        
        // Update statistics
        updateStatistics();
        
        // Load user subscriptions
        loadUserSubscriptions();
        
        // Set up view toggle functionality
        setupViewToggle();
        
        // Set up table sorting
        setupTableSorting();
        
    } catch (error) {
        console.error('Error initializing train dashboard:', error);
        showMessage('Error loading train data', 'error');
        
        // Hide loading spinner on error
        const loadingSpinner = document.getElementById('loadingSpinner');
        if (loadingSpinner) {
            loadingSpinner.style.display = 'none';
        }
    }
}

function setupViewToggle() {
    const viewToggles = document.querySelectorAll('.btn-toggle');
    const tableContainer = document.getElementById('trainTableContainer');
    const cardContainer = document.getElementById('trainListContainer');
    
    viewToggles.forEach(toggle => {
        toggle.addEventListener('click', () => {
            // Remove active class from all toggles
            viewToggles.forEach(t => t.classList.remove('active'));
            // Add active class to clicked toggle
            toggle.classList.add('active');
            
            const view = toggle.getAttribute('data-view');
            
            if (view === 'table') {
                if (tableContainer) tableContainer.style.display = 'block';
                if (cardContainer) cardContainer.style.display = 'none';
            } else if (view === 'card') {
                if (tableContainer) tableContainer.style.display = 'none';
                if (cardContainer) cardContainer.style.display = 'flex';
            }
        });
    });
}

async function fetchAvailableTrains() {
    const info = await trainApiCall('/');
    if (info && info.available_trains) {
        // Strip the "train_" prefix to get just the numbers
        availableTrains = info.available_trains.map(train => train.replace('train_', ''));
        console.log(`Found ${availableTrains.length} trains: ${availableTrains.join(', ')}`);
    } else {
        // Fallback to default trains if API is not available
        availableTrains = ['11014', '12244', '12269', '12322', '12433'];
        console.log('Using fallback train list');
    }
}

function renderTrainCards() {
    if (!trainListContainer) return;
    
    trainListContainer.innerHTML = '';
    
    if (availableTrains.length === 0) {
        trainListContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">
                    <i class="fas fa-train"></i>
                </div>
                <h3>No Trains Available</h3>
                <p>No train information is currently available. Check back later or contact system administrator.</p>
            </div>
        `;
        return;
    }
    
    availableTrains.forEach(train_id => {
        const trainItem = createTrainCard(train_id);
        trainListContainer.appendChild(trainItem);
    });
}

function renderTrainTable() {
    const tableBody = document.getElementById('trainsTableBody');
    if (!tableBody) return;
    
    tableBody.innerHTML = '';
    
    if (availableTrains.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="7" class="empty-state">
                    <div class="empty-state-icon">
                        <i class="fas fa-train"></i>
                    </div>
                    <h3>No Trains Available</h3>
                    <p>No train information is currently available. Check back later or contact system administrator.</p>
                </td>
            </tr>
        `;
        return;
    }
    
    availableTrains.forEach(train_id => {
        const trainRow = createTrainRow(train_id);
        tableBody.appendChild(trainRow);
    });
}

function createTrainRow(train_id) {
    const row = document.createElement('tr');
    row.id = `train-row-${train_id}`;
    
    const data = trainStatusCache[train_id] || {};
    const isSubscribed = userSubscriptions.some(sub => sub.train_number === train_id && sub.is_active);
    
    row.innerHTML = `
        <td class="train-number-cell">
            <div class="train-number-info">
                <div class="train-number">Train ${train_id}</div>
                <div class="train-name" id="trainName-${train_id}">${data.train_name || 'Loading...'}</div>
            </div>
        </td>
        <td class="route-cell">
            <div class="route-info">
                <div class="route-station">
                    <div class="station-name" id="sourceStation-${train_id}">${data.source_stn_name || 'Source'}</div>
                    <div class="station-time" id="sourceTime-${train_id}">--:--</div>
                </div>
                <div class="route-arrow">
                    <i class="fas fa-arrow-right"></i>
                </div>
                <div class="route-station">
                    <div class="station-name" id="destStation-${train_id}">${data.dest_stn_name || 'Destination'}</div>
                    <div class="station-time" id="destTime-${train_id}">--:--</div>
                </div>
            </div>
        </td>
        <td class="current-station-cell">
            <div class="station-badge">
                <span id="currentStation-${train_id}">${data.current_station_name || 'Loading...'}</span>
                <span class="station-code" id="currentStationCode-${train_id}">${data.current_station_code || 'N/A'}</span>
            </div>
        </td>
        <td class="progress-cell">
            <div class="progress-container">
                <div class="progress-bar">
                    <div class="progress-fill" id="progressBar-${train_id}" style="width: 0%"></div>
                </div>
                <div class="progress-text" id="progressText-${train_id}">0%</div>
                <div class="progress-distance" id="progressDistance-${train_id}">0/0 km</div>
            </div>
        </td>
        <td class="status-cell">
            <div class="status-badge status-running" id="statusBadge-${train_id}">
                <div class="status-indicator"></div>
                <span>Active</span>
            </div>
        </td>
        <td class="update-cell">
            <div class="update-time" id="lastUpdate-${train_id}">Never</div>
        </td>
        <td class="actions-cell">
            <div class="action-buttons">
                <button onclick="toggleTrainSubscription('${train_id}')" class="btn-action btn-primary" id="subscribeBtn-${train_id}">
                    <i class="fas fa-bell"></i>
                    ${isSubscribed ? 'Unsubscribe' : 'Subscribe'}
                </button>
            </div>
        </td>
    `;
    
    return row;
}

function createTrainCard(train_id) {
    const trainItem = document.createElement('div');
    trainItem.className = 'train-item';
    trainItem.id = `train-${train_id}`;
    
    trainItem.innerHTML = `
        <div class="train-header">
            <div class="train-number">
                <i class="fas fa-train"></i>
                <span id="trainTitle-${train_id}">Train ${train_id}</span>
            </div>
            <div class="train-status status-running" id="statusBadge-${train_id}">
                Active
            </div>
        </div>
        
        <div class="train-route">
            <div class="route-station">
                <div class="station-name" id="sourceStation-${train_id}">Source</div>
                <div class="station-time" id="sourceTime-${train_id}">--:--</div>
            </div>
            <div class="route-arrow">
                <i class="fas fa-arrow-right"></i>
            </div>
            <div class="route-station">
                <div class="station-name" id="destStation-${train_id}">Destination</div>
                <div class="station-time" id="destTime-${train_id}">--:--</div>
            </div>
        </div>
        
        <div class="train-details">
            <div class="train-detail">
                <div class="train-detail-label">Current Station</div>
                <div class="train-detail-value" id="currentStation-${train_id}">Loading...</div>
            </div>
            <div class="train-detail">
                <div class="train-detail-label">Progress</div>
                <div class="train-detail-value">
                    <span id="progressText-${train_id}">0%</span>
                </div>
            </div>
            <div class="train-detail">
                <div class="train-detail-label">Last Update</div>
                <div class="train-detail-value" id="lastUpdate-${train_id}">Never</div>
            </div>
        </div>
        
        <div class="train-actions">
            <button onclick="toggleTrainSubscription('${train_id}')" class="btn-action btn-primary" id="subscribeBtn-${train_id}">
                <i class="fas fa-bell"></i> Subscribe
            </button>
        </div>
    `;
    
    return trainItem;
}

async function loadTrainStatus() {
    if (availableTrains.length === 0) return;
    
    console.log('Loading train status information...');
    
    try {
        await Promise.all(availableTrains.map(async (train_id) => {
            await loadTrainData(train_id);
        }));
        
        console.log('Train status loaded successfully');
        // Update statistics after loading all train data
        updateStatistics();
    } catch (error) {
        console.error('Error loading train status:', error);
        showMessage('Error loading train data', 'error');
    }
}

// Statistics Update Function
function updateStatistics() {
    // Calculate statistics
    trainStats.total = availableTrains.length;
    trainStats.onTime = 0;
    trainStats.delayed = 0;
    trainStats.cancelled = 0;
    
    // Count trains by status (this is sample logic - adapt based on your actual status logic)
    availableTrains.forEach(train_id => {
        const statusElement = document.getElementById(`statusBadge-${train_id}`);
        if (statusElement) {
            const statusText = statusElement.textContent.toLowerCase();
            if (statusText.includes('active') || statusText.includes('running')) {
                trainStats.onTime++;
            } else if (statusText.includes('delayed')) {
                trainStats.delayed++;
            } else if (statusText.includes('cancelled')) {
                trainStats.cancelled++;
            } else {
                // Default to on-time for unknown status
                trainStats.onTime++;
            }
        } else {
            // Default to on-time if no status found
            trainStats.onTime++;
        }
    });
    
    // Update DOM elements
    const totalElement = document.getElementById('totalTrains');
    const onTimeElement = document.getElementById('onTimeTrains');
    const delayedElement = document.getElementById('delayedTrains');
    const cancelledElement = document.getElementById('cancelledTrains');
    
    if (totalElement) {
        animateCounter(totalElement, trainStats.total);
    }
    if (onTimeElement) {
        animateCounter(onTimeElement, trainStats.onTime);
    }
    if (delayedElement) {
        animateCounter(delayedElement, trainStats.delayed);
    }
    if (cancelledElement) {
        animateCounter(cancelledElement, trainStats.cancelled);
    }
}

// Counter animation function
function animateCounter(element, target) {
    const current = parseInt(element.textContent) || 0;
    const increment = target > current ? 1 : -1;
    const duration = 1000; // 1 second
    const steps = Math.abs(target - current);
    const stepDuration = duration / Math.max(steps, 1);
    
    let counter = current;
    const timer = setInterval(() => {
        counter += increment;
        element.textContent = counter;
        
        if (counter === target) {
            clearInterval(timer);
        }
    }, stepDuration);
}

// Train Subscription functionality
async function loadUserSubscriptions() {
    if (!subscriptionsContainer) return;
    
    try {
        const headers = getAuthHeaders();
        if (!headers) {
            window.location.href = '/';
            return;
        }

        // Get user's current subscriptions
        const response = await fetch('/api/train-subscription/list', {
            method: 'GET',
            headers: headers
        });

        if (response.ok) {
            const data = await response.json();
            userSubscriptions = data.subscriptions || [];
            renderSubscriptions();
            updateSubscriptionButtons();
        } else {
            console.error('Failed to load subscriptions');
            userSubscriptions = [];
            renderSubscriptions();
        }
    } catch (error) {
        console.error('Error loading subscriptions:', error);
        userSubscriptions = [];
        renderSubscriptions();
    }
}

function renderSubscriptions() {
    if (!subscriptionsContainer) return;
    
    if (userSubscriptions.length === 0) {
        subscriptionsContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">
                    <i class="fas fa-bell-slash"></i>
                </div>
                <h3>No Train Subscriptions</h3>
                <p>You haven't subscribed to any train notifications yet. Subscribe to trains above to get real-time updates on Telegram.</p>
            </div>
        `;
        return;
    }
    
    subscriptionsContainer.innerHTML = userSubscriptions.map(subscription => `
        <div class="subscription-item" id="subscription-${subscription.train_number}">
            <div class="subscription-header">
                <div class="subscription-title">
                    <i class="fas fa-train"></i>
                    Train ${subscription.train_number}${subscription.train_name ? ` - ${subscription.train_name}` : ''}
                </div>
                <div class="subscription-actions">
                    <span class="subscription-priority ${subscription.is_active ? 'subscription-active' : 'subscription-inactive'}">
                        ${subscription.is_active ? 'Active' : 'Inactive'}
                    </span>
                    <span class="subscription-status">Subscribed ${formatSubscriptionDate(subscription.subscribed_at)}</span>
                </div>
            </div>
            <div class="subscription-content">
                You will receive real-time notifications for this train on Telegram in your preferred language.
                The subscription will automatically end when the train reaches its destination.
            </div>
            <div class="subscription-actions">
                <button onclick="unsubscribeFromTrain('${subscription.train_number}')" class="btn-unsubscribe">
                    <i class="fas fa-bell-slash"></i>
                    Unsubscribe
                </button>
                ${getTrainElement(subscription.train_number) ? `
                    <button onclick="scrollToTrain('${subscription.train_number}')" class="btn-action btn-secondary">
                        <i class="fas fa-train"></i>
                        View Train
                    </button>
                ` : ''}
            </div>
        </div>
    `).join('');
}

function formatSubscriptionDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = Math.abs(now - date);
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
    const diffHours = Math.floor(diffTime / (1000 * 60 * 60));
    const diffMinutes = Math.floor(diffTime / (1000 * 60));
    
    if (diffDays > 0) {
        return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    } else if (diffHours > 0) {
        return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
    } else if (diffMinutes > 0) {
        return `${diffMinutes} minute${diffMinutes > 1 ? 's' : ''} ago`;
    } else {
        return 'Just now';
    }
}

function updateSubscriptionButtons() {
    // Update all train subscription buttons based on current subscriptions
    availableTrains.forEach(train_id => {
        const isSubscribed = userSubscriptions.some(sub => sub.train_number === train_id && sub.is_active);
        
        // Update table view button
        const tableButton = document.getElementById(`subscribeBtn-${train_id}`);
        if (tableButton) {
            if (isSubscribed) {
                tableButton.innerHTML = '<i class="fas fa-bell-slash"></i> Unsubscribe';
                tableButton.className = 'btn-action btn-unsubscribe';
            } else {
                tableButton.innerHTML = '<i class="fas fa-bell"></i> Subscribe';
                tableButton.className = 'btn-action btn-primary';
            }
        }
        
        // Update legacy card view button if it exists
        const cardButton = document.querySelector(`#train-${train_id} .btn-primary, #train-${train_id} .btn-unsubscribe`);
        if (cardButton) {
            if (isSubscribed) {
                cardButton.innerHTML = '<i class="fas fa-bell-slash"></i> Unsubscribe';
                cardButton.className = 'btn-action btn-unsubscribe';
            } else {
                cardButton.innerHTML = '<i class="fas fa-bell"></i> Subscribe';
                cardButton.className = 'btn-action btn-primary';
            }
        }
    });
}

async function toggleTrainSubscription(trainId) {
    const isSubscribed = userSubscriptions.some(sub => sub.train_number === trainId && sub.is_active);
    
    if (isSubscribed) {
        await unsubscribeFromTrain(trainId);
    } else {
        await subscribeToTrain(trainId);
    }
}

async function subscribeToTrain(trainId) {
    try {
        const headers = getAuthHeaders();
        if (!headers) {
            window.location.href = '/';
            return;
        }

        // Get train name from the UI
        const trainTitleElement = document.getElementById(`trainTitle-${trainId}`);
        const trainName = trainTitleElement ? trainTitleElement.textContent.split(' - ')[1] : null;

        const response = await fetch('/api/train-subscription/subscribe', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
                train_number: trainId,
                train_name: trainName
            })
        });

        const data = await response.json();

        if (response.ok) {
            showMessage(`Successfully subscribed to train ${trainId}!`, 'success');
            
            // Add to local subscriptions
            userSubscriptions.push({
                train_number: trainId,
                train_name: trainName,
                is_active: true,
                subscribed_at: new Date().toISOString()
            });
            
            // Update UI
            renderSubscriptions();
            updateSubscriptionButtons();
            
            // Check if user has Telegram linked
            await checkTelegramStatus();
            
        } else {
            throw new Error(data.detail || 'Failed to subscribe to train');
        }
    } catch (error) {
        console.error('Error subscribing to train:', error);
        showMessage(`Failed to subscribe to train ${trainId}: ${error.message}`, 'error');
    }
}

async function unsubscribeFromTrain(trainId) {
    try {
        const headers = getAuthHeaders();
        if (!headers) {
            window.location.href = '/';
            return;
        }

        const response = await fetch(`/api/train-subscription/unsubscribe/${trainId}`, {
            method: 'DELETE',
            headers: headers
        });

        const data = await response.json();

        if (response.ok) {
            showMessage(`Successfully unsubscribed from train ${trainId}!`, 'success');
            
            // Remove from local subscriptions
            userSubscriptions = userSubscriptions.filter(sub => sub.train_number !== trainId);
            
            // Update UI
            renderSubscriptions();
            updateSubscriptionButtons();
            
        } else {
            throw new Error(data.detail || 'Failed to unsubscribe from train');
        }
    } catch (error) {
        console.error('Error unsubscribing from train:', error);
        showMessage(`Failed to unsubscribe from train ${trainId}: ${error.message}`, 'error');
    }
}

async function checkTelegramStatus() {
    try {
        const headers = getAuthHeaders();
        if (!headers) return;

        const response = await fetch('/api/telegram/status', {
            method: 'GET',
            headers: headers
        });

        if (response.ok) {
            const data = await response.json();
            if (!data.linked) {
                showMessage('Link your Telegram account in Profile to receive notifications', 'info');
            }
        }
    } catch (error) {
        console.error('Error checking Telegram status:', error);
    }
}

function getTrainElement(trainId) {
    return document.getElementById(`train-${trainId}`);
}

function scrollToTrain(trainId) {
    const trainElement = getTrainElement(trainId);
    if (trainElement) {
        trainElement.scrollIntoView({ 
            behavior: 'smooth', 
            block: 'center' 
        });
        
        // Highlight the train item briefly
        trainElement.style.background = 'linear-gradient(135deg, #dbeafe 0%, #f0f9ff 100%)';
        trainElement.style.borderColor = '#3b82f6';
        
        setTimeout(() => {
            trainElement.style.background = '';
            trainElement.style.borderColor = '';
        }, 2000);
        
        showMessage(`Scrolled to train ${trainId}`, 'info');
    } else {
        showMessage(`Train ${trainId} not found`, 'error');
    }
}

async function loadTrainData(train_id) {
    try {
        // Try to load from train API (add train_ prefix for API call)
        const status = await trainApiCall(`/api/train/status?train_id=train_${train_id}`);
        if (status && status.data) {
            updateTrainDisplay(train_id, status.data);
            updateTrainStatus(train_id, true);
        } else {
            // Load sample data if API is not available
            loadSampleTrainData(train_id);
        }
        
    } catch (error) {
        console.error(`Error loading train ${train_id}:`, error);
        // Load sample data as fallback
        loadSampleTrainData(train_id);
    }
}

function loadSampleTrainData(train_id) {
    // Sample train data for display
    const sampleData = {
        '11014': {
            train_number: '11014',
            train_name: 'Lokmanya Tilak Express',
            source_stn_name: 'Mumbai',
            dest_stn_name: 'Delhi',
            current_station_name: 'Pune Junction',
            current_station_code: 'PUNE',
            distance_from_source: 150,
            total_distance: 1200,
            update_time: new Date().toLocaleTimeString()
        },
        '12244': {
            train_number: '12244',
            train_name: 'Bengaluru Rajdhani',
            source_stn_name: 'New Delhi',
            dest_stn_name: 'Bengaluru',
            current_station_name: 'Hyderabad',
            current_station_code: 'HYB',
            distance_from_source: 800,
            total_distance: 2000,
            update_time: new Date().toLocaleTimeString()
        },
        '12269': {
            train_number: '12269',
            train_name: 'Chennai Duronto',
            source_stn_name: 'New Delhi',
            dest_stn_name: 'Chennai Central',
            current_station_name: 'Vijayawada',
            current_station_code: 'BZA',
            distance_from_source: 1200,
            total_distance: 1700,
            update_time: new Date().toLocaleTimeString()
        },
        '12322': {
            train_number: '12322',
            train_name: 'Howrah Mail',
            source_stn_name: 'Mumbai',
            dest_stn_name: 'Kolkata',
            current_station_name: 'Nagpur',
            current_station_code: 'NGP',
            distance_from_source: 800,
            total_distance: 1900,
            update_time: new Date().toLocaleTimeString()
        },
        '12433': {
            train_number: '12433',
            train_name: 'Rajdhani Express',
            source_stn_name: 'New Delhi',
            dest_stn_name: 'Ahmedabad',
            current_station_name: 'Jaipur',
            current_station_code: 'JP',
            distance_from_source: 300,
            total_distance: 900,
            update_time: new Date().toLocaleTimeString()
        }
    };
    
    const data = sampleData[train_id];
    if (data) {
        updateTrainDisplay(train_id, data);
        updateTrainStatus(train_id, true);
    }
}

function updateTrainDisplay(train_id, data) {
    if (!data) return;
    
    // Update table view elements
    const trainNameElement = document.getElementById(`trainName-${train_id}`);
    if (trainNameElement) {
        trainNameElement.textContent = data.train_name || 'Unknown';
    }
    
    // Update current station in table
    const currentStationElement = document.getElementById(`currentStation-${train_id}`);
    const currentStationCodeElement = document.getElementById(`currentStationCode-${train_id}`);
    if (currentStationElement) {
        currentStationElement.textContent = data.current_station_name || 'Unknown';
    }
    if (currentStationCodeElement) {
        currentStationCodeElement.textContent = data.current_station_code || 'N/A';
    }
    
    // Update progress in table
    const progress = Math.round((data.distance_from_source / data.total_distance) * 100) || 0;
    const progressBarElement = document.getElementById(`progressBar-${train_id}`);
    const progressTextElement = document.getElementById(`progressText-${train_id}`);
    const progressDistanceElement = document.getElementById(`progressDistance-${train_id}`);
    
    if (progressBarElement) {
        progressBarElement.style.width = `${progress}%`;
    }
    if (progressTextElement) {
        progressTextElement.textContent = `${progress}%`;
    }
    if (progressDistanceElement) {
        progressDistanceElement.textContent = `${data.distance_from_source || 0}/${data.total_distance || 0} km`;
    }
    
    // Update legacy card view elements (for backward compatibility)
    const titleElement = document.getElementById(`trainTitle-${train_id}`);
    if (titleElement) {
        titleElement.textContent = `${data.train_number} - ${data.train_name}`;
    }
    
    // Update source station
    const sourceStationElement = document.getElementById(`sourceStation-${train_id}`);
    if (sourceStationElement) {
        sourceStationElement.textContent = data.source_stn_name;
    }
    
    // Update destination station
    const destStationElement = document.getElementById(`destStation-${train_id}`);
    if (destStationElement) {
        destStationElement.textContent = data.dest_stn_name;
    }
    
    // Update current station in legacy view
    const legacyCurrentStationElement = document.querySelector(`#train-${train_id} .train-detail-value`);
    if (legacyCurrentStationElement) {
        legacyCurrentStationElement.textContent = `${data.current_station_name} (${data.current_station_code})`;
    }
    
    // Update progress in legacy view
    const legacyProgressTextElement = document.querySelector(`#train-${train_id} #progressText-${train_id}`);
    if (legacyProgressTextElement) {
        legacyProgressTextElement.textContent = `${progress}% (${data.distance_from_source}/${data.total_distance} km)`;
    }
    
    // Update last update time
    const lastUpdateElements = document.querySelectorAll(`#lastUpdate-${train_id}`);
    lastUpdateElements.forEach(element => {
        element.textContent = data.update_time || 'Never';
    });
    
    // Cache the data
    trainStatusCache[train_id] = data;
}

function updateTrainStatus(train_id, isRunning) {
    const statusBadge = document.getElementById(`statusBadge-${train_id}`);
    if (!statusBadge) return;
    
    const indicator = statusBadge.querySelector('.status-indicator');
    
    if (isRunning) {
        indicator.className = 'status-indicator status-connected';
        statusBadge.innerHTML = `
            <span class="status-indicator status-connected"></span>
            Running
        `;
        statusBadge.className = 'status-badge badge-running';
    } else {
        indicator.className = 'status-indicator status-disconnected';
        statusBadge.innerHTML = `
            <span class="status-indicator status-disconnected"></span>
            Stopped
        `;
        statusBadge.className = 'status-badge badge-stopped';
    }
}

function updateTrainStatus(train_id, isActive) {
    const statusBadge = document.getElementById(`statusBadge-${train_id}`);
    if (!statusBadge) return;
    
    const indicator = statusBadge.querySelector('.status-indicator');
    
    if (isActive) {
        indicator.className = 'status-indicator status-connected';
        statusBadge.innerHTML = `
            <span class="status-indicator status-connected"></span>
            Active
        `;
        statusBadge.className = 'status-badge badge-running';
    } else {
        indicator.className = 'status-indicator status-info';
        statusBadge.innerHTML = `
            <span class="status-indicator status-info"></span>
            Scheduled
        `;
        statusBadge.className = 'status-badge badge-scheduled';
    }
}

function playTrainAnnouncement(train_id) {
    const data = trainStatusCache[train_id];
    if (!data) {
        showMessage('No train data available for announcement', 'error');
        return;
    }
    
    const announcementText = `Attention passengers! Train number ${data.train_number}, ${data.train_name}, is currently at ${data.current_station_name}. The train is traveling from ${data.source_stn_name} to ${data.dest_stn_name}.`;
    
    handleTrainAnnouncement(announcementText, null);
}

function viewTrainDetails(train_id) {
    const data = trainStatusCache[train_id];
    if (!data) {
        showMessage('No train data available', 'error');
        return;
    }
    
    // Create a modal or detailed view
    const modal = document.createElement('div');
    modal.className = 'train-modal';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3>${data.train_name} (${data.train_number})</h3>
                <button onclick="this.parentElement.parentElement.parentElement.remove()" class="modal-close">×</button>
            </div>
            <div class="modal-body">
                <div class="detail-row">
                    <strong>Route:</strong> ${data.source_stn_name} → ${data.dest_stn_name}
                </div>
                <div class="detail-row">
                    <strong>Current Station:</strong> ${data.current_station_name} (${data.current_station_code})
                </div>
                <div class="detail-row">
                    <strong>Distance Covered:</strong> ${data.distance_from_source} km
                </div>
                <div class="detail-row">
                    <strong>Total Distance:</strong> ${data.total_distance} km
                </div>
                <div class="detail-row">
                    <strong>Last Updated:</strong> ${data.update_time}
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
}

function loadSavedLanguage() {
    const savedLanguage = localStorage.getItem('selectedLanguage');
    if (savedLanguage && targetLanguagesSelect) {
        // Check if the saved language still exists in the options
        const option = targetLanguagesSelect.querySelector(`option[value="${savedLanguage}"]`);
        if (option) {
            targetLanguagesSelect.value = savedLanguage;
            selectedLanguage = savedLanguage;
            showMessage(`Welcome back! Language set to ${getLanguageName(savedLanguage)}`, 'info');
        } else {
            // Remove invalid saved language
            localStorage.removeItem('selectedLanguage');
        }
    }
}

async function getCurrentUser() {
    const headers = getAuthHeaders();
    if (!headers) {
        console.log('No auth headers, redirecting to login');
        window.location.href = '/';
        return;
    }

    try {
        const response = await fetch('/me', { headers });
        
        if (response.ok) {
            currentUser = await response.json();
            welcomeMessage.textContent = `Welcome, ${currentUser.username}!`;
            console.log('User authenticated successfully:', currentUser.username);
        } else if (response.status === 401) {
            console.log('Token expired or invalid, redirecting to login');
            localStorage.removeItem('access_token');
            localStorage.removeItem('selectedLanguage');
            window.location.href = '/';
        } else {
            throw new Error(`HTTP ${response.status}: Failed to get user info`);
        }
    } catch (error) {
        console.error('Get user error:', error);
        // Only redirect on auth errors, not network errors
        if (error.message.includes('401') || error.message.includes('Unauthorized')) {
            localStorage.removeItem('access_token');
            localStorage.removeItem('selectedLanguage');
            window.location.href = '/';
        } else {
            showMessage('Network error. Please check your connection and refresh.', 'error');
        }
    }
}

async function loadSupportedLanguages() {
    try {
        const response = await fetch('/supported-languages');
        const data = await response.json();
        supportedLanguages = data.languages;
        
        populateLanguageSelects();
    } catch (error) {
        console.error('Failed to load languages:', error);
        showMessage('Failed to load supported languages', 'error');
    }
}

function populateLanguageSelects() {
    if (!targetLanguagesSelect) {
        return;
    }

    // Clear existing options
    targetLanguagesSelect.innerHTML = '<option value="">Select announcement language...</option>';

    // Populate target languages select
    Object.entries(supportedLanguages).forEach(([code, name]) => {
        const targetOption = document.createElement('option');
        targetOption.value = code;
        targetOption.textContent = `${name} (${code})`;
        targetLanguagesSelect.appendChild(targetOption);
    });
}

// Utility functions
function showMessage(message, type = 'info') {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    messageDiv.textContent = message;
    
    messageContainer.innerHTML = '';
    messageContainer.appendChild(messageDiv);
    
    // Auto-hide success messages after 5 seconds
    if (type === 'success') {
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.remove();
            }
        }, 5000);
    }
    
    // Scroll to message
    messageDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function clearMessages() {
    messageContainer.innerHTML = '';
}

function showLoading(show = true) {
    loadingIndicator.style.display = show ? 'block' : 'none';
}

function getLanguageName(code) {
    return supportedLanguages[code] || code;
}

// Event handlers
function handleLogout() {
    console.log('Logging out from dashboard');
    localStorage.removeItem('access_token');
    localStorage.removeItem('selectedLanguage');
    showMessage('Logged out successfully', 'success');
    setTimeout(() => {
        window.location.href = '/';
    }, 1000);
}

async function handleTrainAnnouncement(announcementText, announcementCard) {
    if (!selectedLanguage) {
        showMessage('Please select a language first', 'error');
        return;
    }
    
    // Clear previous active states
    document.querySelectorAll('.announcement-card').forEach(card => {
        card.classList.remove('active');
    });
    
    // Mark current card as active
    announcementCard.classList.add('active');
    
    clearMessages();
    
    const headers = getAuthHeaders();
    if (!headers) return;
    
    try {
        // Show loading
        showLoading(true);
        
        const response = await fetch('/generate-audio', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({
                text: announcementText,
                language: selectedLanguage
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            showAudioSection(data, announcementText);
            showMessage('Announcement generated successfully!', 'success');
        } else {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'Failed to generate announcement');
        }
    } catch (error) {
        console.error('Announcement generation error:', error);
        showMessage(`Error: ${error.message}`, 'error');
        announcementCard.classList.remove('active');
    } finally {
        showLoading(false);
    }
}

function showAudioSection(audioData, text) {
    audioLanguage.textContent = getLanguageName(selectedLanguage);
    audioText.textContent = text;
    audioPlayer.src = audioData.audio_url;
    audioSection.style.display = 'block';
    
    // Scroll to audio section
    audioSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
    
    // Set up download functionality
    downloadBtn.onclick = () => {
        const link = document.createElement('a');
        link.href = audioData.audio_url;
        link.download = `train_announcement_${Date.now()}.mp3`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };
}

function showNewAudioForm() {
    audioSection.style.display = 'none';
    document.querySelectorAll('.announcement-card').forEach(card => {
        card.classList.remove('active');
    });
    showMessage('Select another train announcement', 'info');
}

// Utility functions
function showMessage(message, type = 'info') {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}`;
    messageDiv.textContent = message;
    
    messageContainer.innerHTML = '';
    messageContainer.appendChild(messageDiv);
    
    // Auto-hide success messages after 5 seconds
    if (type === 'success') {
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.remove();
            }
        }, 5000);
    }
    
    // Scroll to message
    messageDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function clearMessages() {
    messageContainer.innerHTML = '';
}

function showLoading(show = true) {
    loadingIndicator.style.display = show ? 'block' : 'none';
}

function getLanguageName(code) {
    return supportedLanguages[code] || code;
}

// Authentication helper
function getAuthHeaders() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = '/';
        return null;
    }
    return {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
    };
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Escape to hide audio section
    if (e.key === 'Escape') {
        audioSection.style.display = 'none';
        document.querySelectorAll('.announcement-card').forEach(card => {
            card.classList.remove('active');
        });
        clearMessages();
    }
    
    // Numbers 1-5 to trigger announcements
    if (e.key >= '1' && e.key <= '5' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const announcementNumber = parseInt(e.key);
        const announcementCard = document.querySelector(`[data-announcement="${announcementNumber}"]`);
        if (announcementCard) {
            const announcementBtn = announcementCard.querySelector('.announcement-btn');
            if (announcementBtn) {
                announcementBtn.click();
            }
        }
    }
});

// User Preferences Functions
async function loadUserPreferences() {
    try {
        const response = await fetch('/api/user/preferences', {
            method: 'GET',
            headers: getAuthHeaders()
        });

        if (response.ok) {
            const preferences = await response.json();
            
            // Update UI with current preferences
            if (preferredLanguageSelect) {
                preferredLanguageSelect.value = preferences.preferred_language || 'en';
            }
            
            if (audioNotificationsCheckbox) {
                audioNotificationsCheckbox.checked = preferences.audio_notifications || false;
            }
            
            console.log('User preferences loaded:', preferences);
        } else {
            console.error('Failed to load preferences');
        }
    } catch (error) {
        console.error('Error loading preferences:', error);
    }
}

// ESSENTIAL UTILITY FUNCTIONS

function handleLogout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('username');
    localStorage.removeItem('selectedLanguage');
    localStorage.removeItem('preferredLanguage');
    localStorage.removeItem('audioNotifications');
    window.location.href = '/';
}

function showNewAudioForm() {
    audioSection.style.display = 'none';
    showMessage('Select an announcement to generate audio', 'info');
}

function getLanguageName(code) {
    return supportedLanguages[code] || code;
}

// Add table sorting functionality
function setupTableSorting() {
    const sortableHeaders = document.querySelectorAll('.sortable');
    
    sortableHeaders.forEach(header => {
        header.addEventListener('click', () => {
            const sortColumn = header.getAttribute('data-sort');
            sortTable(sortColumn);
        });
    });
}

function sortTable(column) {
    const tableBody = document.getElementById('trainsTableBody');
    if (!tableBody) return;
    
    const rows = Array.from(tableBody.querySelectorAll('tr'));
    
    rows.sort((a, b) => {
        let aValue, bValue;
        
        switch (column) {
            case 'train_number':
                aValue = a.querySelector('.train-number').textContent.replace('Train ', '');
                bValue = b.querySelector('.train-number').textContent.replace('Train ', '');
                return parseInt(aValue) - parseInt(bValue);
                
            case 'current_station':
                const aId = a.id.split('-')[2];
                const bId = b.id.split('-')[2];
                aValue = a.querySelector(`#currentStation-${aId}`).textContent;
                bValue = b.querySelector(`#currentStation-${bId}`).textContent;
                return aValue.localeCompare(bValue);
                
            case 'progress':
                aValue = parseFloat(a.querySelector('.progress-text').textContent.replace('%', ''));
                bValue = parseFloat(b.querySelector('.progress-text').textContent.replace('%', ''));
                return aValue - bValue;
                
            case 'status':
                aValue = a.querySelector('.status-badge span').textContent;
                bValue = b.querySelector('.status-badge span').textContent;
                return aValue.localeCompare(bValue);
                
            case 'last_update':
                aValue = a.querySelector('.update-time').textContent;
                bValue = b.querySelector('.update-time').textContent;
                return aValue.localeCompare(bValue);
                
            default:
                return 0;
        }
    });
    
    // Clear table body and re-append sorted rows
    tableBody.innerHTML = '';
    rows.forEach(row => tableBody.appendChild(row));
}
