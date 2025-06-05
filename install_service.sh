#!/usr/bin/env fish

# Install required packages if not already installed
echo "Checking and installing dependencies..."
pip3 install -r requirements.txt

# Copy the service file to systemd directory
echo "Installing service file..."
sudo cp music-scheduler.service /etc/systemd/system/

# Reload systemd to recognize the new service
echo "Reloading systemd..."
sudo systemctl daemon-reload

# Enable and start the service
echo "Enabling and starting service..."
sudo systemctl enable music-scheduler.service
sudo systemctl restart music-scheduler.service

# Check service status
echo "Service status:"
sudo systemctl status music-scheduler.service

echo "Done! If you encounter any issues, check the logs with:"
echo "sudo journalctl -u music-scheduler.service -f"
