#!/usr/bin/env python3
"""
Mock Train Status API Server
Serves train status data with automatic location updates to simulate real-time train movement.
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import threading
import time
from datetime import datetime, timedelta

import copy
import os
import glob
import random

app = Flask(__name__)
CORS(app)

class TrainStatusSimulator:
    def __init__(self, json_file_path):
        self.json_file_path = json_file_path
        self.train_data = self.load_train_data()
        self.original_data = copy.deepcopy(self.train_data)
        self.current_station_index = 0
        self.update_interval = 30  # seconds between updates
        self.is_running = False
        self.stations_list = []
        self.subscribers = set()  # Set of subscriber IDs/emails
        self.auto_restart = True  # Auto-restart when train reaches destination
        self.restart_delay = 60  # Delay before restart in seconds
        self._extract_stations()
        
    def load_train_data(self):
        """Load train data from JSON file"""
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: {self.json_file_path} not found")
            return {}
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            return {}
    
    def _extract_stations(self):
        """Extract all stations in order from the train data"""
        if not self.train_data or 'data' not in self.train_data:
            return
            
        data = self.train_data['data']
        
        # Get all stations from previous_stations and upcoming_stations
        previous = data.get('previous_stations', [])
        current_code = data.get('current_station_code')
        upcoming = data.get('upcoming_stations', [])
        
        # Combine all stations in order
        all_stations = []
        
        # Add previous stations
        for station in previous:
            all_stations.append({
                'si_no': station['si_no'],
                'code': station['station_code'],
                'name': station['station_name'],
                'distance': station['distance_from_source'],
                'lat': station.get('station_lat'),
                'lng': station.get('station_lng'),
                'sta': station.get('sta', ''),
                'std': station.get('std', ''),
                'status': 'completed'
            })
        
        # Add current station
        if current_code:
            current_station = {
                'si_no': data.get('si_no'),
                'code': current_code,
                'name': data.get('current_station_name'),
                'distance': data.get('distance_from_source'),
                'lat': None,
                'lng': None,
                'sta': data.get('cur_stn_sta', ''),
                'std': data.get('cur_stn_std', ''),
                'status': 'current'
            }
            all_stations.append(current_station)
        
        # Add upcoming stations
        for station in upcoming:
            all_stations.append({
                'si_no': station['si_no'],
                'code': station['station_code'],
                'name': station['station_name'],
                'distance': station['distance_from_source'],
                'lat': station.get('station_lat'),
                'lng': station.get('station_lng'),
                'sta': station.get('sta', ''),
                'std': station.get('std', ''),
                'status': 'upcoming'
            })
        
        self.stations_list = sorted(all_stations, key=lambda x: x['si_no'])
        
        # Find current station index
        for i, station in enumerate(self.stations_list):
            if station['status'] == 'current':
                self.current_station_index = i
                break
    
    def set_random_starting_position(self):
        """Set train to a random starting position along the route"""
        if not self.stations_list:
            return
        
        # Choose a random station (excluding the last few stations to allow movement)
        max_index = max(0, len(self.stations_list) - 3)
        random_index = random.randint(0, max_index)
        
        self.current_station_index = random_index
        current_station = self.stations_list[random_index]
        
        # Update train data to reflect new position
        data = self.train_data['data']
        data['current_station_code'] = current_station['code']
        data['current_station_name'] = current_station['name']
        data['distance_from_source'] = current_station['distance']
        data['si_no'] = current_station['si_no']
        
        # Update timing
        now = datetime.now()
        data['update_time'] = now.strftime("%Y-%m-%d %H:%M:%S +0530")
        self.train_data['timestamp'] = int(now.timestamp() * 1000)
        
        # Rebuild previous and upcoming stations based on new position
        self._rebuild_station_lists()
        
        print(f"Train positioned at random station: {current_station['name']} ({current_station['code']}) - Index: {random_index}")
    
    def _rebuild_station_lists(self):
        """Rebuild previous and upcoming station lists based on current position"""
        data = self.train_data['data']
        previous_stations = []
        upcoming_stations = []
        
        for i, station in enumerate(self.stations_list):
            if i < self.current_station_index:
                # Previous stations
                station_data = {
                    "si_no": station['si_no'],
                    "station_code": station['code'],
                    "station_name": station['name'],
                    "is_diverted_station": False,
                    "distance_from_source": station['distance'],
                    "sta": station['sta'],
                    "std": station['std'],
                    "eta": station['sta'],
                    "etd": station['std'],
                    "halt": 2,
                    "a_day": 1,
                    "arrival_delay": 0,
                    "platform_number": 1,
                    "stoppage_number": i + 1,
                    "non_stops": []
                }
                if station['lat'] and station['lng']:
                    station_data['station_lat'] = station['lat']
                    station_data['station_lng'] = station['lng']
                previous_stations.append(station_data)
            elif i > self.current_station_index:
                # Upcoming stations
                current_station = self.stations_list[self.current_station_index]
                distance_from_current = station['distance'] - current_station['distance']
                station_data = {
                    "si_no": station['si_no'],
                    "station_code": station['code'],
                    "station_name": station['name'],
                    "is_diverted_station": False,
                    "distance_from_source": station['distance'],
                    "distance_from_current_station": distance_from_current,
                    "distance_from_current_station_txt": f"Next stop {distance_from_current} kms to go",
                    "sta": station['sta'],
                    "std": station['std'],
                    "eta": station['sta'],
                    "etd": station['std'],
                    "halt": 2,
                    "a_day": 1,
                    "arrival_delay": 0,
                    "platform_number": 1,
                    "on_time_rating": 6,
                    "stoppage_number": i + 1,
                    "day": 1,
                    "eta_a_min": 2000 + (i * 30),
                    "food_available": False,
                    "non_stops": []
                }
                if station['lat'] and station['lng']:
                    station_data['station_lat'] = station['lat']
                    station_data['station_lng'] = station['lng']
                upcoming_stations.append(station_data)
        
        data['previous_stations'] = previous_stations
        data['upcoming_stations'] = upcoming_stations
        
        # Update current station timing
        current_station = self.stations_list[self.current_station_index]
        data['cur_stn_sta'] = current_station['sta']
        data['cur_stn_std'] = current_station['std']
        data['eta'] = current_station['sta']
        data['etd'] = current_station['std']
    
    def update_train_position(self):
        """Update train position to next station"""
        if not self.stations_list or self.current_station_index >= len(self.stations_list) - 1:
            # Train has reached destination
            final_station = self.stations_list[-1] if self.stations_list else {"name": "Unknown", "code": "UNK"}
            
            print(f"🏁 Train has reached destination: {final_station['name']} ({final_station['code']})!")
            
            # Notify subscribers about journey completion
            completion_message = f"Journey completed! Train has reached final destination: {final_station['name']} ({final_station['code']})"
            self.notify_subscribers(completion_message, "journey_completed")
            
            # Unsubscribe all passengers
            unsubscribe_result = self.unsubscribe_all_passengers()
            
            # Handle auto-restart
            if self.auto_restart:
                print(f"⏰ Auto-restart enabled. Train will restart in {self.restart_delay} seconds...")
                
                # Schedule restart in a separate thread
                def delayed_restart():
                    time.sleep(self.restart_delay)
                    if self.is_running:  # Only restart if simulation is still supposed to be running
                        print("🔄 Auto-restarting train with new random route...")
                        self.reset_simulation()
                        restart_message = f"Train restarted! New journey begins from {self.train_data.get('data', {}).get('current_station_name')}"
                        self.notify_subscribers(restart_message, "journey_started")
                
                restart_thread = threading.Thread(target=delayed_restart, daemon=True)
                restart_thread.start()
                
                # Return True to keep simulation running for auto-restart
                return True
            else:
                print("🛑 Auto-restart disabled. Simulation will stop.")
                return False
        
        # Move to next station (normal operation)
        self.current_station_index += 1
        next_station = self.stations_list[self.current_station_index]
        
        # Update train data
        data = self.train_data['data']
        
        # Update current position
        data['current_station_code'] = next_station['code']
        data['current_station_name'] = next_station['name']
        data['distance_from_source'] = next_station['distance']
        data['si_no'] = next_station['si_no']
        
        # Update timing
        now = datetime.now()
        data['update_time'] = now.strftime("%Y-%m-%d %H:%M:%S +0530")
        self.train_data['timestamp'] = int(now.timestamp() * 1000)
        
        # Update previous and upcoming stations
        previous_stations = []
        upcoming_stations = []
        
        for i, station in enumerate(self.stations_list):
            if i < self.current_station_index:
                # Previous stations
                station_data = {
                    "si_no": station['si_no'],
                    "station_code": station['code'],
                    "station_name": station['name'],
                    "is_diverted_station": False,
                    "distance_from_source": station['distance'],
                    "sta": station['sta'],
                    "std": station['std'],
                    "eta": station['sta'],
                    "etd": station['std'],
                    "halt": 2,
                    "a_day": 1,
                    "arrival_delay": 0,
                    "platform_number": 1,
                    "stoppage_number": i + 1,
                    "non_stops": []
                }
                if station['lat'] and station['lng']:
                    station_data['station_lat'] = station['lat']
                    station_data['station_lng'] = station['lng']
                previous_stations.append(station_data)
            elif i > self.current_station_index:
                # Upcoming stations
                distance_from_current = station['distance'] - next_station['distance']
                station_data = {
                    "si_no": station['si_no'],
                    "station_code": station['code'],
                    "station_name": station['name'],
                    "is_diverted_station": False,
                    "distance_from_source": station['distance'],
                    "distance_from_current_station": distance_from_current,
                    "distance_from_current_station_txt": f"Next stop {distance_from_current} kms to go",
                    "sta": station['sta'],
                    "std": station['std'],
                    "eta": station['sta'],
                    "etd": station['std'],
                    "halt": 2,
                    "a_day": 1,
                    "arrival_delay": 0,
                    "platform_number": 1,
                    "on_time_rating": 6,
                    "stoppage_number": i + 1,
                    "day": 1,
                    "eta_a_min": 2000 + (i * 30),
                    "food_available": False,
                    "non_stops": []
                }
                if station['lat'] and station['lng']:
                    station_data['station_lat'] = station['lat']
                    station_data['station_lng'] = station['lng']
                upcoming_stations.append(station_data)
        
        data['previous_stations'] = previous_stations
        data['upcoming_stations'] = upcoming_stations
        
        # Update current station timing
        data['cur_stn_sta'] = next_station['sta']
        data['cur_stn_std'] = next_station['std']
        data['eta'] = next_station['sta']
        data['etd'] = next_station['std']
        
        # Update status message
        remaining_distance = data['total_distance'] - next_station['distance']
        data['ahead_distance'] = min(5, remaining_distance)  # Random distance ahead
        data['ahead_distance_text'] = f"{data['ahead_distance']} kms ahead"
        data['status_as_of'] = "As of 1 min ago"
        data['status_as_of_min'] = 1
        
        print(f"Train moved to: {next_station['name']} ({next_station['code']})")
        return True
    
    def start_simulation(self):
        """Start the train position simulation"""
        self.is_running = True
        
        def simulation_loop():
            while self.is_running:
                time.sleep(self.update_interval)
                if not self.update_train_position():
                    # Train reached destination and auto-restart is disabled
                    self.is_running = False
                    print("🛑 Train simulation stopped - destination reached and auto-restart disabled.")
                    break
        
        thread = threading.Thread(target=simulation_loop, daemon=True)
        thread.start()
        print(f"🚂 Train simulation started. Updates every {self.update_interval} seconds.")
        if self.auto_restart:
            print(f"🔄 Auto-restart enabled with {self.restart_delay}s delay after reaching destination.")
        else:
            print("🛑 Auto-restart disabled - simulation will stop at destination.")
    
    def stop_simulation(self):
        """Stop the train position simulation"""
        self.is_running = False
        print("Train simulation stopped.")
    
    def reset_simulation(self):
        """Reset train to original position and then set to a new random position"""
        self.train_data = copy.deepcopy(self.original_data)
        self.current_station_index = 0
        self._extract_stations()
        # Set a new random starting position after reset
        self.set_random_starting_position()
        print("Train simulation reset to a new random position.")
    
    def get_train_status(self):
        """Get current train status"""
        return self.train_data
    
    def set_update_interval(self, seconds):
        """Set update interval in seconds"""
        self.update_interval = max(5, seconds)  # Minimum 5 seconds
        print(f"Update interval set to {self.update_interval} seconds")
    
    def add_subscriber(self, subscriber_id):
        """Add a subscriber/passenger to the train"""
        self.subscribers.add(subscriber_id)
        print(f"Subscriber {subscriber_id} added to train. Total subscribers: {len(self.subscribers)}")
        return True
    
    def remove_subscriber(self, subscriber_id):
        """Remove a subscriber/passenger from the train"""
        if subscriber_id in self.subscribers:
            self.subscribers.remove(subscriber_id)
            print(f"Subscriber {subscriber_id} removed from train. Total subscribers: {len(self.subscribers)}")
            return True
        return False
    
    def get_subscribers(self):
        """Get list of all subscribers"""
        return list(self.subscribers)
    
    def notify_subscribers(self, message, event_type="info"):
        """Notify all subscribers about train events"""
        if not self.subscribers:
            return
        
        notification = {
            "timestamp": datetime.now().isoformat(),
            "train_id": os.path.splitext(os.path.basename(self.json_file_path))[0],
            "event_type": event_type,
            "message": message,
            "current_station": {
                "code": self.train_data.get('data', {}).get('current_station_code'),
                "name": self.train_data.get('data', {}).get('current_station_name')
            },
            "subscribers": list(self.subscribers)
        }
        
        print(f"📢 NOTIFICATION [{event_type.upper()}]: {message}")
        print(f"   👥 Notified {len(self.subscribers)} subscribers: {list(self.subscribers)}")
        # In a real implementation, you would send notifications via email/SMS/push notifications
        # For now, we'll just log them
        
        return notification
    
    def unsubscribe_all_passengers(self):
        """Unsubscribe all passengers when train journey ends"""
        if self.subscribers:
            unsubscribed_count = len(self.subscribers)
            unsubscribed_list = list(self.subscribers)
            self.subscribers.clear()
            
            message = f"Journey completed! All {unsubscribed_count} passengers have been unsubscribed."
            print(f"🎯 {message}")
            print(f"   📝 Unsubscribed passengers: {unsubscribed_list}")
            
            return {
                "unsubscribed_count": unsubscribed_count,
                "unsubscribed_passengers": unsubscribed_list,
                "message": message
            }
        return {"unsubscribed_count": 0, "unsubscribed_passengers": [], "message": "No passengers to unsubscribe"}
    
    def set_auto_restart(self, enabled, restart_delay=60):
        """Configure auto-restart behavior"""
        self.auto_restart = enabled
        self.restart_delay = max(10, restart_delay)  # Minimum 10 seconds delay
        print(f"Auto-restart {'enabled' if enabled else 'disabled'}. Restart delay: {self.restart_delay} seconds")
        return True


# Multi-train support: load all train JSON files from /data/trains/
TRAINS_DIR = os.path.join(os.path.dirname(__file__), 'data', 'trains')
train_simulators = {}


def load_all_trains():
    train_simulators.clear()
    for json_path in glob.glob(os.path.join(TRAINS_DIR, '*.json')):
        train_id = os.path.splitext(os.path.basename(json_path))[0]  # e.g., 'train_22638'
        sim = TrainStatusSimulator(json_path)
        # Assign a random update interval between 20 and 60 seconds
        sim.set_update_interval(random.randint(20, 60))
        # Set a random starting position for each train
        sim.set_random_starting_position()
        train_simulators[train_id] = sim
    print(f"Loaded {len(train_simulators)} trains: {list(train_simulators.keys())}")

load_all_trains()


# Helper to get simulator by train_id
def get_simulator(train_id):
    sim = train_simulators.get(train_id)
    if not sim:
        return None
    return sim

# API endpoints now require train_id as a query parameter or path
@app.route('/api/train/status', methods=['GET'])
def get_train_status():
    """Get current train status for a train_id (query param)"""
    train_id = request.args.get('train_id')
    sim = get_simulator(train_id)
    if not sim:
        return jsonify({'error': f'Train {train_id} not found'}), 404
    return jsonify(sim.get_train_status())


@app.route('/api/train/start', methods=['POST'])
def start_simulation():
    """Start train movement simulation for a train_id (JSON body or query param)"""
    data = request.get_json(silent=True) or {}
    train_id = data.get('train_id') or request.args.get('train_id')
    sim = get_simulator(train_id)
    if not sim:
        return jsonify({'error': f'Train {train_id} not found'}), 404
    sim.start_simulation()
    return jsonify({
        "status": "success",
        "message": f"Train {train_id} simulation started",
        "update_interval": sim.update_interval
    })


@app.route('/api/train/stop', methods=['POST'])
def stop_simulation():
    """Stop train movement simulation for a train_id"""
    data = request.get_json(silent=True) or {}
    train_id = data.get('train_id') or request.args.get('train_id')
    sim = get_simulator(train_id)
    if not sim:
        return jsonify({'error': f'Train {train_id} not found'}), 404
    sim.stop_simulation()
    return jsonify({
        "status": "success",
        "message": f"Train {train_id} simulation stopped"
    })


@app.route('/api/train/reset', methods=['POST'])
def reset_simulation():
    """Reset train to original position for a train_id"""
    data = request.get_json(silent=True) or {}
    train_id = data.get('train_id') or request.args.get('train_id')
    sim = get_simulator(train_id)
    if not sim:
        return jsonify({'error': f'Train {train_id} not found'}), 404
    sim.reset_simulation()
    return jsonify({
        "status": "success",
        "message": f"Train {train_id} simulation reset to original position"
    })


@app.route('/api/train/config', methods=['POST'])
def configure_simulation():
    """Configure simulation parameters for a train_id"""
    data = request.get_json() or {}
    train_id = data.get('train_id') or request.args.get('train_id')
    sim = get_simulator(train_id)
    if not sim:
        return jsonify({'error': f'Train {train_id} not found'}), 404
    
    # Update interval
    if 'update_interval' in data:
        sim.set_update_interval(data['update_interval'])
    
    # Auto-restart configuration
    if 'auto_restart' in data:
        sim.set_auto_restart(data['auto_restart'], data.get('restart_delay', sim.restart_delay))
    elif 'restart_delay' in data:
        sim.set_auto_restart(sim.auto_restart, data['restart_delay'])
    
    return jsonify({
        "status": "success",
        "message": "Configuration updated",
        "current_config": {
            "update_interval": sim.update_interval,
            "is_running": sim.is_running,
            "auto_restart": sim.auto_restart,
            "restart_delay": sim.restart_delay,
            "subscriber_count": len(sim.subscribers),
            "current_station": {
                "code": sim.train_data.get('data', {}).get('current_station_code'),
                "name": sim.train_data.get('data', {}).get('current_station_name')
            }
        }
    })


@app.route('/api/train/stations', methods=['GET'])
def get_stations_list():
    """Get list of all stations in the route for a train_id"""
    train_id = request.args.get('train_id')
    sim = get_simulator(train_id)
    if not sim:
        return jsonify({'error': f'Train {train_id} not found'}), 404
    return jsonify({
        "status": "success",
        "total_stations": len(sim.stations_list),
        "current_station_index": sim.current_station_index,
        "stations": sim.stations_list
    })


@app.route('/api/train/random-position', methods=['POST'])
def set_random_position():
    """Set train to a random position for a train_id"""
    data = request.get_json(silent=True) or {}
    train_id = data.get('train_id') or request.args.get('train_id')
    sim = get_simulator(train_id)
    if not sim:
        return jsonify({'error': f'Train {train_id} not found'}), 404
    sim.set_random_starting_position()
    return jsonify({
        "status": "success",
        "message": f"Train {train_id} moved to random position",
        "current_station": {
            "code": sim.train_data.get('data', {}).get('current_station_code'),
            "name": sim.train_data.get('data', {}).get('current_station_name'),
            "index": sim.current_station_index
        }
    })


@app.route('/api/train/move', methods=['POST'])
def manual_move():
    """Manually move train to next station for a train_id"""
    data = request.get_json(silent=True) or {}
    train_id = data.get('train_id') or request.args.get('train_id')
    sim = get_simulator(train_id)
    if not sim:
        return jsonify({'error': f'Train {train_id} not found'}), 404
    success = sim.update_train_position()
    if success:
        return jsonify({
            "status": "success",
            "message": f"Train {train_id} moved to next station",
            "current_station": {
                "code": sim.train_data.get('data', {}).get('current_station_code'),
                "name": sim.train_data.get('data', {}).get('current_station_name')
            }
        })
    else:
        return jsonify({
            "status": "error",
            "message": f"Train {train_id} has reached destination"
        })


@app.route('/api/train/subscribe', methods=['POST'])
def subscribe_passenger():
    """Subscribe a passenger to train notifications"""
    data = request.get_json() or {}
    train_id = data.get('train_id') or request.args.get('train_id')
    passenger_id = data.get('passenger_id') or data.get('email') or data.get('user_id')
    
    if not passenger_id:
        return jsonify({'error': 'passenger_id, email, or user_id is required'}), 400
    
    sim = get_simulator(train_id)
    if not sim:
        return jsonify({'error': f'Train {train_id} not found'}), 404
    
    sim.add_subscriber(passenger_id)
    
    # Send welcome notification
    welcome_message = f"Welcome aboard! You are now subscribed to updates for train {train_id}"
    sim.notify_subscribers(welcome_message, "subscription_confirmed")
    
    return jsonify({
        "status": "success",
        "message": f"Passenger {passenger_id} subscribed to train {train_id}",
        "passenger_id": passenger_id,
        "train_id": train_id,
        "total_subscribers": len(sim.subscribers)
    })


@app.route('/api/train/unsubscribe', methods=['POST'])
def unsubscribe_passenger():
    """Unsubscribe a passenger from train notifications"""
    data = request.get_json() or {}
    train_id = data.get('train_id') or request.args.get('train_id')
    passenger_id = data.get('passenger_id') or data.get('email') or data.get('user_id')
    
    if not passenger_id:
        return jsonify({'error': 'passenger_id, email, or user_id is required'}), 400
    
    sim = get_simulator(train_id)
    if not sim:
        return jsonify({'error': f'Train {train_id} not found'}), 404
    
    success = sim.remove_subscriber(passenger_id)
    
    if success:
        return jsonify({
            "status": "success",
            "message": f"Passenger {passenger_id} unsubscribed from train {train_id}",
            "passenger_id": passenger_id,
            "train_id": train_id,
            "total_subscribers": len(sim.subscribers)
        })
    else:
        return jsonify({
            "status": "error",
            "message": f"Passenger {passenger_id} was not subscribed to train {train_id}"
        })


@app.route('/api/train/subscribers', methods=['GET'])
def get_subscribers():
    """Get list of all subscribers for a train"""
    train_id = request.args.get('train_id')
    sim = get_simulator(train_id)
    if not sim:
        return jsonify({'error': f'Train {train_id} not found'}), 404
    
    return jsonify({
        "status": "success",
        "train_id": train_id,
        "subscribers": sim.get_subscribers(),
        "total_subscribers": len(sim.subscribers)
    })


@app.route('/api/train/auto-restart', methods=['POST'])
def configure_auto_restart():
    """Configure auto-restart behavior for a train"""
    data = request.get_json() or {}
    train_id = data.get('train_id') or request.args.get('train_id')
    enabled = data.get('enabled', True)
    restart_delay = data.get('restart_delay', 60)
    
    sim = get_simulator(train_id)
    if not sim:
        return jsonify({'error': f'Train {train_id} not found'}), 404
    
    sim.set_auto_restart(enabled, restart_delay)
    
    return jsonify({
        "status": "success",
        "message": f"Auto-restart {'enabled' if enabled else 'disabled'} for train {train_id}",
        "train_id": train_id,
        "auto_restart": enabled,
        "restart_delay": sim.restart_delay
    })


@app.route('/api/train/unsubscribe-all', methods=['POST'])
def unsubscribe_all_passengers():
    """Unsubscribe all passengers from a train (manual trigger)"""
    data = request.get_json(silent=True) or {}
    train_id = data.get('train_id') or request.args.get('train_id')
    
    sim = get_simulator(train_id)
    if not sim:
        return jsonify({'error': f'Train {train_id} not found'}), 404
    
    result = sim.unsubscribe_all_passengers()
    
    return jsonify({
        "status": "success",
        "train_id": train_id,
        **result
    })


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint, returns status for all trains"""
    train_status = {}
    for tid, sim in train_simulators.items():
        train_status[tid] = {
            "simulation_running": sim.is_running,
            "auto_restart_enabled": sim.auto_restart,
            "restart_delay": sim.restart_delay,
            "subscriber_count": len(sim.subscribers),
            "current_station": {
                "code": sim.train_data.get('data', {}).get('current_station_code'),
                "name": sim.train_data.get('data', {}).get('current_station_name')
            },
            "station_index": f"{sim.current_station_index + 1}/{len(sim.stations_list)}"
        }
    
    return jsonify({
        "status": "healthy",
        "service": "Mock Train API with Auto-Restart",
        "timestamp": datetime.now().isoformat(),
        "total_trains": len(train_simulators),
        "trains": train_status
    })


@app.route('/', methods=['GET'])
def home():
    """API documentation"""
    return jsonify({
        "service": "Mock Train Status API with Auto-Restart & Passenger Management",
        "version": "3.0.0",
        "description": "A mock API that serves train status data for multiple trains with automatic location updates, auto-restart functionality, and passenger notification management",
        "endpoints": {
            "GET /api/train/status?train_id=...": "Get current train status",
            "POST /api/train/start {train_id: ...}": "Start automatic train movement simulation",
            "POST /api/train/stop {train_id: ...}": "Stop automatic train movement simulation",
            "POST /api/train/reset {train_id: ...}": "Reset train to a new random position",
            "POST /api/train/random-position {train_id: ...}": "Set train to a random position",
            "POST /api/train/config {train_id: ..., update_interval: ...}": "Configure simulation (update_interval)",
            "GET /api/train/stations?train_id=...": "Get list of all stations",
            "POST /api/train/move {train_id: ...}": "Manually move train to next station",
            "POST /api/train/subscribe {train_id: ..., passenger_id: ...}": "Subscribe passenger to train notifications",
            "POST /api/train/unsubscribe {train_id: ..., passenger_id: ...}": "Unsubscribe passenger from train notifications",
            "GET /api/train/subscribers?train_id=...": "Get list of train subscribers",
            "POST /api/train/auto-restart {train_id: ..., enabled: ..., restart_delay: ...}": "Configure auto-restart behavior",
            "POST /api/train/unsubscribe-all {train_id: ...}": "Unsubscribe all passengers from train",
            "GET /api/health": "Health check (all trains with detailed status)"
        },
        "features": {
            "auto_restart": "Trains automatically restart with new random route when reaching destination",
            "passenger_management": "Subscribe/unsubscribe passengers for notifications",
            "notifications": "Automatic notifications for journey events (completion, restart, etc.)",
            "multi_train_support": "Support for multiple trains with individual configurations"
        },
        "examples": {
            "start_simulation": "POST /api/train/start {\"train_id\": \"train_22638\"}",
            "configure": "POST /api/train/config {\"train_id\": \"train_22638\", \"update_interval\": 60}",
            "get_status": "GET /api/train/status?train_id=train_22638",
            "subscribe_passenger": "POST /api/train/subscribe {\"train_id\": \"train_22638\", \"passenger_id\": \"user123@email.com\"}",
            "configure_auto_restart": "POST /api/train/auto-restart {\"train_id\": \"train_22638\", \"enabled\": true, \"restart_delay\": 120}",
            "unsubscribe_passenger": "POST /api/train/unsubscribe {\"train_id\": \"train_22638\", \"passenger_id\": \"user123@email.com\"}"
        },
        "available_trains": list(train_simulators.keys())
    })



if __name__ == '__main__':
    print("=" * 70)
    print("🚂 Mock Train Status API Server (Auto-Restart + Passenger Management)")
    print("=" * 70)
    print(f"📂 Loading data from: {TRAINS_DIR}")
    print(f"📊 Loaded {len(train_simulators)} trains: {list(train_simulators.keys())}")
    for tid, sim in train_simulators.items():
        current_station = sim.train_data.get('data', {}).get('current_station_name')
        station_index = sim.current_station_index
        total_stations = len(sim.stations_list)
        auto_restart_status = "✅ ENABLED" if sim.auto_restart else "❌ DISABLED"
        print(f"  - {tid}: {total_stations} stations, starting at: {current_station} (#{station_index+1}/{total_stations})")
        print(f"    ⏱️  Update interval: {sim.update_interval}s | 🔄 Auto-restart: {auto_restart_status} ({sim.restart_delay}s delay)")
    print("=" * 70)
    print("🌐 Core API Endpoints:")
    print("   GET  /api/train/status?train_id=...  - Get current train status")
    print("   POST /api/train/start {train_id: ...} - Start simulation")
    print("   POST /api/train/stop  {train_id: ...} - Stop simulation")
    print("   POST /api/train/reset {train_id: ...} - Reset to new random position")
    print("   POST /api/train/move  {train_id: ...} - Move to next station")
    print("   GET  /api/train/stations?train_id=... - List all stations")
    print("")
    print("👥 Passenger Management Endpoints:")
    print("   POST /api/train/subscribe {train_id, passenger_id} - Subscribe passenger")
    print("   POST /api/train/unsubscribe {train_id, passenger_id} - Unsubscribe passenger")
    print("   GET  /api/train/subscribers?train_id=... - List subscribers")
    print("   POST /api/train/unsubscribe-all {train_id} - Unsubscribe all passengers")
    print("")
    print("🔄 Auto-Restart Configuration:")
    print("   POST /api/train/auto-restart {train_id, enabled, restart_delay} - Configure auto-restart")
    print("")
    print("💡 Features:")
    print("   🔄 Auto-restart: Trains automatically restart with new random routes")
    print("   📢 Notifications: Passengers get notified about journey events")
    print("   👥 Passenger management: Subscribe/unsubscribe for notifications")
    print("   🎯 Auto-unsubscribe: All passengers are unsubscribed when journey ends")
    print("=" * 70)

    # Automatically start all train simulations with their random intervals
    for tid, sim in train_simulators.items():
        sim.start_simulation()
        restart_status = f"with auto-restart ({sim.restart_delay}s delay)" if sim.auto_restart else "without auto-restart"
        print(f"[AUTO-START] Train {tid} simulation started - interval: {sim.update_interval}s, {restart_status}")

    print("🚀 Starting server on http://localhost:5001")
    print("   Use Ctrl+C to stop the server")
    print("=" * 70)
    app.run(host='0.0.0.0', port=5001, debug=False)
