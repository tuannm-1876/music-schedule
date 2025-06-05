// Disk usage monitoring
function updateDiskUsage() {
    fetch('/get-disk-usage')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const diskUsage = data.data;
                
                // Update the disk usage bar
                const diskFill = document.querySelector('.disk-usage-fill');
                if (diskFill) {
                    diskFill.style.width = `${diskUsage.percentage_used}%`;
                    
                    // Update color based on percentage
                    if (diskUsage.percentage_used >= 90) {
                        diskFill.style.backgroundColor = 'var(--disk-high)';
                    } else if (diskUsage.percentage_used >= 70) {
                        diskFill.style.backgroundColor = 'var(--disk-medium)';
                    } else {
                        diskFill.style.backgroundColor = 'var(--disk-low)';
                    }
                }
                
                // Update percentage text
                const percentageElement = document.querySelector('.disk-usage-percentage');
                if (percentageElement) {
                    percentageElement.textContent = `${diskUsage.percentage_used}%`;
                }
                
                // Update details
                const detailsContainer = document.querySelector('.disk-usage-item div');
                if (detailsContainer) {
                    detailsContainer.innerHTML = `
                        <span>Used: ${diskUsage.used_gb} GB</span>
                        <span>Free: ${diskUsage.free_gb} GB</span>
                        <span>Total: ${diskUsage.total_gb} GB</span>
                    `;
                }
            }
        })
        .catch(error => {
            console.error('Error updating disk usage:', error);
        });
}

// Update disk usage every 60 seconds
document.addEventListener('DOMContentLoaded', function() {
    // Initial update
    updateDiskUsage();
    
    // Schedule regular updates
    setInterval(updateDiskUsage, 60000);
});
