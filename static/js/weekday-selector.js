// Handle weekday selection UI
document.addEventListener('DOMContentLoaded', function() {
    // Find all checkboxes in the weekday selection
    const weekdayCheckboxes = document.querySelectorAll('.weekday-selection input[type="checkbox"]');
    
    // Add event listeners to each checkbox
    weekdayCheckboxes.forEach(checkbox => {
        // Initial setup
        updateLabelClass(checkbox);
        
        // Handle changes
        checkbox.addEventListener('change', function() {
            updateLabelClass(this);
        });
    });
    
    // Update label classes based on checkbox state
    function updateLabelClass(checkbox) {
        const label = checkbox.closest('label');
        if (checkbox.checked) {
            label.classList.add('selected');
        } else {
            label.classList.remove('selected');
        }
    }
});
