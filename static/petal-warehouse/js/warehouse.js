angular.module('droneWarehouseApp', [])
.controller('DroneController', ['$http', '$timeout', function($http, $timeout) {
    var vm = this;
    // Initialize properties
    vm.currentCommand = '';
    vm.lastResponse = null;
    vm.isProcessing = false;
    vm.isRecording = false;
    vm.systemStatus = 'ready';
    vm.commandHistory = [];
    vm.serverUrl = 'http://localhost:9000/petals/petal-warehouse'; // Default FastAPI server URL
    vm.voiceStatus = {
        show: false,
        message: '',
        type: ''
    };
    vm.responseCollapsed = true;
    vm.transcriptionCollapsed = true;
    vm.textCmdCollapsed = true;
    vm.examplesExpanded = false; // already collapsed by default
    vm.historyCollapsed = true;
    vm.transcriptionCollapsed = true;
    vm.exampleCommands = [
        "Show me the last scanned item in rack 4",
        "There is an obstacle around rack 6",
        "Where is the item with barcode 2531?",
        "The maintenance around rack 6 has ended",
        "Show me all items that were scanned 2 days ago",
        "Show me the restricted areas in the warehouse",
        "Scan shelves A, B, and C in racks 4 and 5",
        "Where is the drone now?"
    ];

    vm.animatedTranscribedText = '';

    var currentAudio = null;

    // Browser-based voice recording state
    vm.isBrowserRecording = false;
    vm.browserMediaRecorder = null;
    vm.browserAudioChunks = [];

    // Add to your controller in <script>:
    vm.floatingCmdOpen = false;
    vm.floatingCmdText = '';
    vm.handleFloatingCmdKey = function(event) {
        if (event.keyCode === 13 && !event.shiftKey) { // Enter key without Shift
            event.preventDefault();
            var cmd = vm.floatingCmdText.trim();
            if (cmd) {
                vm.sendFloatingCommand(cmd);
                vm.floatingCmdText = '';
                vm.floatingCmdOpen = false;
            }
        }
    };

    vm.isTranscribedInput = false;

    // Show spoken transcription in floating window
    vm.transcriptionWindowText = '';

    vm.sendFloatingCommand = function(command) {
        vm.isProcessing = true;
        vm.systemStatus = 'processing';
        vm.lastResponse = null;
        vm.showVoiceStatus('Sending the command...', 'processing');
        $timeout(vm.hideVoiceStatus, 2000);

        vm.commandHistory.push({
            command: command,
            timestamp: new Date()
        });

        $http.post(vm.getServerUrl() + '/process_command', {
            command: command
        }, {
            headers: {
                'Content-Type': 'application/json'
            }
        }).then(function(response) {
            vm.lastResponse = response.data;
            vm.openResponseWindow(); // <-- Open and auto-close after 5s
            vm.systemStatus = response.data.status === 'error' ? 'error' : 'ready';

            // --- FIX: Play TTS audio if generated ---
            if (response.data.audio_generated) {
                if (currentAudio && !currentAudio.paused) {
                    currentAudio.pause();
                    currentAudio.currentTime = 0;
                }
                currentAudio = new Audio(vm.getServerUrl() + '/audio/output.mp3?ts=' + new Date().getTime());
                currentAudio.addEventListener('canplaythrough', function() {
                    currentAudio.play().catch(function(err) {
                        console.error('Audio playback failed:', err);
                    });
                });
                currentAudio.load();
            }
            // --- END FIX ---

        }).catch(function(error) {
            vm.lastResponse = {
                status: 'error',
                message: 'Connection Error: Unable to connect to the FastAPI server.\n\nPlease ensure:\n• The FastAPI server is running at: ' + vm.getServerUrl() + '\n• Your Python backend is properly configured\n• The server URL is correct\n\nError details: ' + (error.message || 'Unknown error'),
                timestamp: new Date().toISOString()
            };
            vm.systemStatus = 'error';
        }).finally(function() {
            vm.isProcessing = false;
        });
    };

    // Helper method to get the current server URL
    vm.getServerUrl = function() {
        return vm.serverUrl.replace(/\/$/, ''); // Remove trailing slash
    };

    vm.showTranscriptionWindow = function(text) {
        vm.transcriptionWindowText = text;
        vm.transcriptionCollapsed = false; // Open the window
        // Auto-close after 3 seconds
        $timeout(function() {
            vm.transcriptionCollapsed = true;
        }, 5000);
    };

    // Call this after transcription:
    vm.animateTranscribedText = function(text) {
        vm.currentCommand = '';
        vm.isTranscribedInput = true;
        let prefix = 'You said: ';
        let i = 0;
        vm.showTranscriptionWindow(text); // <-- show in floating window
        function typeChar() {
            if (i < prefix.length) {
                vm.currentCommand += prefix.charAt(i);
                i++;
                $timeout(typeChar, 80);
            } else if (i - prefix.length < text.length) {
                vm.currentCommand += text.charAt(i - prefix.charAt(i - prefix.length));
                i++;
                $timeout(typeChar, 80);
            }
        }
        typeChar();
    };

    // Voice control methods - using custom recorder
    vm.handleVoiceCommand = function() {
        // Always pause any currently playing audio before starting/stopping recording
        if (currentAudio && !currentAudio.paused) {
            currentAudio.pause();
            currentAudio.currentTime = 0;
        }
        if (vm.isRecording) {
            // Stop recording and transcribe only
            vm.showVoiceStatus('Analyzing Speech...', 'processing');
            vm.isRecording = false;
            $http.post(vm.getServerUrl() + '/transcribe_command', {}, {
                headers: { 'Content-Type': 'application/json' }
            }).then(function(response) {
                if (response.data && response.data.transcribed_text) {
                    vm.animateTranscribedText(response.data.transcribed_text);
                    vm.showVoiceStatus('Transcription complete', 'processing');
                    // Hide the "Transcription complete" message after 2 seconds
                    $timeout(function() {
                        vm.hideVoiceStatus();
                    }, 1000);
                    // Now, start processing in background
                    vm.isProcessing = true;
                    $timeout(function() {
                        vm.hideVoiceStatus();
                        vm.showVoiceStatus('Thinking...', 'processing');
                        vm.isProcessing = true;
                        // ...then send the command for processing...
                        $http.post(vm.getServerUrl() + '/process_transcribed_command', {
                            transcribed_text: response.data.transcribed_text
                        }, {
                            headers: { 'Content-Type': 'application/json' }
                        }).then(function(resp) {
                            vm.lastResponse = resp.data;
                            vm.openResponseWindow(); // <-- Open and auto-close after 5s
                            vm.isProcessing = false;
                            vm.systemStatus = resp.data.status === 'error' ? 'error' : 'ready';
                            // Add voice command to history
                            if (resp.data && resp.data.transcribed_text) {
                                vm.commandHistory.push({
                                    command: resp.data.transcribed_text,
                                    timestamp: new Date()
                                });
                            }
                            // Play audio if generated
                            if (resp.data.audio_generated) {
                                if (currentAudio && !currentAudio.paused) {
                                    currentAudio.pause();
                                    currentAudio.currentTime = 0;
                                }
                                currentAudio = new Audio(vm.getServerUrl() + '/audio/output.mp3?ts=' + new Date().getTime());
                                currentAudio.addEventListener('canplaythrough', function() {
                                    currentAudio.play().catch(function(err) {
                                        console.error('Audio playback failed:', err);
                                    });
                                });
                                currentAudio.load();
                            }
                        }, function() {
                            vm.lastResponse = { status: 'error', message: "Error processing command." };
                            vm.isProcessing = false;
                            vm.systemStatus = 'error';
                            vm.hideVoiceStatus();
                        });
                    }, 2000);
                } else {
                    vm.showVoiceStatus('Transcription failed', 'error');
                }
            }, function() {
                vm.showVoiceStatus('Transcription failed', 'error');
            });
        } else {
            // Start recording
            vm.startSpeechRecording();
        }
    };

    vm.startSpeechRecording = function() {
        // Pause any currently playing audio
        if (currentAudio && !currentAudio.paused) {
            currentAudio.pause();
            currentAudio.currentTime = 0;
        }
        vm.isRecording = true;
        vm.showVoiceStatus('Starting recording...', 'processing');
        vm.systemStatus = 'processing';

        $http.post(vm.getServerUrl() + '/start_recording', {}, {
            headers: {
                'Content-Type': 'application/json'
            }
        }).then(function(response) {
            if (response.data.status === 'ok') {
                // vm.showVoiceStatus('Recording... Speak your command', 'listening');
                vm.showVoiceStatus('', 'listening');
            } else {
                vm.showError('Failed to start recording: ' + response.data.message);
                vm.isRecording = false;
                vm.systemStatus = 'error';
            }
        }).catch(function(error) {
            console.error('Error starting recording:', error);
            vm.showError('Failed to start recording. Please check if the FastAPI server is running at: ' + vm.getServerUrl());
            vm.isRecording = false;
            vm.systemStatus = 'error';
        });
    };

    vm.stopSpeechRecording = function() {
        vm.showVoiceStatus('Processing speech...', 'processing');
        vm.isRecording = false;

        $http.post(vm.getServerUrl() + '/handle_speech_commands', {}, {
            headers: {
                'Content-Type': 'application/json'
            }
        }).then(function(response) {
            vm.lastResponse = response.data;
            
            if (response.data.status === 'ok') {
                vm.systemStatus = 'ready';
                // Add transcribed text to command input for reference
                if (response.data.transcribed_text) {
                    vm.animateTranscribedText(response.data.transcribed_text);
                }
                // Add to history
                if (response.data.transcribed_text) {
                    vm.commandHistory.push({
                        command: response.data.transcribed_text,
                        timestamp: new Date()
                    });
                }
            } else if (response.data.status === 'exit') {
                vm.systemStatus = 'ready';
                vm.showVoiceStatus('Session ended', 'processing');
            } else {
                vm.systemStatus = 'error';
            }
            
            $timeout(function() {
                vm.hideVoiceStatus();
            }, 2000);
            
            // Play TTS audio if generated
            if (response.data.audio_generated) {
                var audio = new Audio(vm.getServerUrl() + '/audio/output.mp3?ts=' + new Date().getTime());
                audio.addEventListener('canplaythrough', function() {
                    audio.play().catch(function(err) {
                        console.error('Audio playback failed:', err);
                    });
                });
                audio.load();
            }
            
        }).catch(function(error) {
            console.error('Error processing speech:', error);
            vm.lastResponse = {
                status: 'error',
                message: 'Failed to process speech command. Please check if the FastAPI server is running at: ' + vm.getServerUrl(),
                timestamp: new Date().toISOString()
            };
            vm.systemStatus = 'error';
            vm.isRecording = false;
            
            $timeout(function() {
                vm.hideVoiceStatus();
            }, 2000);
        });
    };

    // Browser-based voice recording methods
    // Toggle browser recording on button click
    vm.toggleBrowserRecording = function(event) {
        if (vm.isBrowserRecording) {
            vm.stopBrowserRecording(event);
        } else {
            vm.startBrowserRecording(event);
        }
    };

    // Start browser recording
    vm.startBrowserRecording = async function(event) {
        if (event) event.preventDefault();
        if (vm.isProcessing || vm.isRecording || vm.isBrowserRecording) return;
        vm.isBrowserRecording = true;
        
        // Show "Listening..." status as soon as recording starts
        vm.showVoiceStatus('Listening... Speak your command!', 'listening');
        
        vm.browserAudioChunks = [];
        let stream;
        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } catch (err) {
            alert('Microphone access is required to use browser voice recording. Please allow access in your browser.');
            vm.isBrowserRecording = false;
            vm.hideVoiceStatus(); // Hide status if mic access fails
            return;
        }
        vm.browserMediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });

        vm.browserMediaRecorder.ondataavailable = function(event) {
            vm.browserAudioChunks.push(event.data);
        };

        vm.browserMediaRecorder.onstop = async function() {
            // Show "Analyzing Speech..." with spinning logo while uploading and processing
            $timeout(function() {
                vm.showVoiceStatus('Analyzing Speech...', 'processing');
            });

            const audioBlob = new Blob(vm.browserAudioChunks, { type: 'audio/webm' });
            const formData = new FormData();
            formData.append('file', audioBlob, 'voice.webm');
            try {
                const response = await fetch(vm.getServerUrl() + '/upload_voice', {
                    method: 'POST',
                    body: formData
                });
                const data = await response.json();
                $timeout(function() {
                    if (data.recognized_text) {
                        // Set transcription text and automatically show the interpreted command window
                        vm.transcriptionWindowText = data.recognized_text;
                        vm.transcriptionCollapsed = false; // Auto-open the interpreted command window
                        
                        vm.animateTranscribedText(data.recognized_text);
                        vm.showVoiceStatus('Transcription complete', 'processing');
                        
                        // Only show "Transcription complete" for half a second (500ms)
                        $timeout(function() {
                            vm.hideVoiceStatus();
                            // Now show "Thinking..." and start processing
                            vm.showVoiceStatus('Thinking...', 'processing');
                            vm.isProcessing = true;
                            
                            // Process the command
                            $http.post(vm.getServerUrl() + '/process_transcribed_command', {
                                transcribed_text: data.recognized_text
                            }, {
                                headers: { 'Content-Type': 'application/json' }
                            }).then(function(resp) {
                                vm.lastResponse = resp.data;
                                vm.openResponseWindow(); // <-- Open and auto-close after 5s
                                vm.isProcessing = false;
                                vm.systemStatus = resp.data.status === 'error' ? 'error' : 'ready';
                                if (resp.data && resp.data.transcribed_text) {
                                    vm.commandHistory.push({
                                        command: resp.data.transcribed_text,
                                        timestamp: new Date()
                                    });
                                }
                                if (resp.data.audio_generated) {
                                    if (currentAudio && !currentAudio.paused) {
                                        currentAudio.pause();
                                        currentAudio.currentTime = 0;
                                    }
                                    currentAudio = new Audio(vm.getServerUrl() + '/audio/output.mp3?ts=' + new Date().getTime());
                                    currentAudio.addEventListener('canplaythrough', function() {
                                        currentAudio.play().catch(function(err) {
                                            console.error('Audio playback failed:', err);
                                        });
                                    });
                                    currentAudio.load();
                                }
                                vm.hideVoiceStatus(); // Hide status after response
                            }, function() {
                                vm.lastResponse = { status: 'error', message: "Error processing command." };
                                vm.isProcessing = false;
                                vm.systemStatus = 'error';
                                vm.hideVoiceStatus();
                            });
                        }, 500); // Show "Transcription complete" for only 500ms
                    } else {
                        vm.showVoiceStatus('Transcription failed', 'error');
                        $timeout(function() {
                            vm.hideVoiceStatus();
                        }, 2000);
                    }
                });
            } catch (err) {
                $timeout(function() {
                    vm.showVoiceStatus('Transcription failed', 'error');
                    $timeout(function() {
                        vm.hideVoiceStatus();
                    }, 2000);
                    vm.lastResponse = {
                        status: 'error',
                        message: 'Failed to process browser voice command: ' + (err.message || err),
                        timestamp: new Date().toISOString()
                    };
                    vm.systemStatus = 'error';
                    vm.isProcessing = false;
                });
            }
        };

        vm.browserMediaRecorder.start();
        $timeout();
        vm.systemStatus = 'processing';
    };

    // Stop browser recording and process
    vm.stopBrowserRecording = function(event) {
        if (event) event.preventDefault();
        if (!vm.browserMediaRecorder || !vm.isBrowserRecording) return;
        vm.isBrowserRecording = false;
        vm.browserMediaRecorder.stop();
        $timeout();
    };

    vm.showVoiceStatus = function(message, type) {
        vm.voiceStatus = {
            show: true,
            message: message,
            type: type || ''
        };
    };

    vm.hideVoiceStatus = function() {
        vm.voiceStatus.show = false;
    };

    // Command handling
    vm.sendCommand = function() {
        var command = vm.currentCommand.trim();
        
        if (!command) {
            vm.showError('Please enter a command.');
            return;
        }

        vm.isProcessing = true;
        vm.systemStatus = 'processing';
        vm.lastResponse = null;

        // Show status for sending text command
        vm.showVoiceStatus('Sending the command...', 'processing');
        $timeout(vm.hideVoiceStatus, 2000); // Hide after 2 seconds

        // Add to history
        vm.commandHistory.push({
            command: command,
            timestamp: new Date()
        });

        $http.post(vm.getServerUrl() + '/process_command', {
            command: command
        }, {
            headers: {
                'Content-Type': 'application/json'
            }
        }).then(function(response) {
            vm.lastResponse = response.data;
            vm.openResponseWindow(); // <-- Open and auto-close after 5s
            vm.systemStatus = response.data.status === 'error' ? 'error' : 'ready';
            vm.currentCommand = '';
            
            // Play TTS audio if generated
            if (response.data.audio_generated) {
                var audio = new Audio(vm.getServerUrl() + '/audio/output.mp3?ts=' + new Date().getTime());
                audio.addEventListener('canplaythrough', function() {
                    audio.play().catch(function(err) {
                        console.error('Audio playback failed:', err);
                    });
                });
                audio.load();
            }
            
        }).catch(function(error) {
            console.error('Error:', error);
            vm.lastResponse = {
                status: 'error',
                message: 'Connection Error: Unable to connect to the FastAPI server.\n\nPlease ensure:\n• The FastAPI server is running at: ' + vm.getServerUrl() + '\n• Your Python backend is properly configured\n• The server URL is correct\n\nError details: ' + (error.message || 'Unknown error'),
                timestamp: new Date().toISOString()
            };
            vm.systemStatus = 'error';
            
        }).finally(function() {
            vm.isProcessing = false;
            // Do NOT call vm.hideVoiceStatus() here!
        });
    };

    vm.launchBlender = function() {
        vm.isProcessing = true;
        vm.systemStatus = 'processing';

        $http.post(vm.getServerUrl() + '/launch_blender', {}, {
            headers: {
                'Content-Type': 'application/json'
            }
        }).then(function(response) {
            vm.lastResponse = response.data;
            vm.systemStatus = 'ready';
            
        }).catch(function(error) {
            console.error('Error:', error);
            vm.lastResponse = {
                status: 'error',
                message: 'Failed to launch Blender. Please check if the FastAPI server is running at: ' + vm.getServerUrl(),
                timestamp: new Date().toISOString()
            };
            vm.systemStatus = 'error';
            
        }).finally(function() {
            vm.isProcessing = false;
        });
    };

    // Keyboard handling
    vm.handleKeyDown = function(event) {
        vm.isTranscribedInput = false;
        if (event.keyCode === 13 && !event.shiftKey) { // Enter key without Shift
            event.preventDefault();
            vm.sendCommand();
        }
    };

    // Toggle example commands visibility
    vm.toggleExamples = function() {
        vm.examplesExpanded = !vm.examplesExpanded;
    };

    // Helper methods
    vm.getStatusText = function() {
        switch (vm.systemStatus) {
            case 'ready': return 'System Ready';
            case 'processing': return 'Processing...';
            case 'error': return 'Error';
            default: return 'Unknown';
        }
    };

    vm.getResponseClass = function() {
        if (!vm.lastResponse) return '';
        
        switch (vm.lastResponse.status) {
            case 'error': return 'error';
            case 'ok': return 'success';
            default: return '';
        }
    };

    vm.showError = function(message) {
        vm.lastResponse = {
            status: 'error',
            message: message,
            timestamp: new Date().toISOString()
        };
        vm.systemStatus = 'error';
    };

    // System status check on load
    vm.checkSystemStatus = function() {
        $http.get(vm.getServerUrl() + '/system_status')
        .then(function(response) {
            console.log('System status:', response.data);
            if (response.data.status !== 'ok') {
                vm.showError('System not fully initialized: ' + response.data.message);
            }
        })
        .catch(function(error) {
            console.warn('Could not check system status:', error);
            vm.showError('Warning: Could not connect to FastAPI server at ' + vm.getServerUrl() + '. Please check the server URL and ensure the server is running.');
        });
    };

    // Check system status on load
    $timeout(function() {
        vm.checkSystemStatus();
    }, 1000);

                // Add this helper function to your controller:
    vm.openResponseWindow = function() {
        vm.responseCollapsed = false; // Open the System Response window
        // Auto-close after 5 seconds
        $timeout(function() {
            vm.responseCollapsed = true;
        }, 7000);
    };
}]);