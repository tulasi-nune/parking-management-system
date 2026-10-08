// Form Validation JavaScript
class FormValidator {
    constructor() {
        this.setupValidation();
    }
    
    setupValidation() {
        // Real-time validation
        document.addEventListener('input', (e) => {
            if (e.target.classList.contains('form-control')) {
                this.validateField(e.target);
            }
        });
        
        // Form submission validation
        document.addEventListener('submit', (e) => {
            if (e.target.classList.contains('validate-form')) {
                if (!this.validateForm(e.target)) {
                    e.preventDefault();
                }
            }
        });
    }
    
    validateField(field) {
        const value = field.value.trim();
        const type = field.type;
        const required = field.hasAttribute('required');
        const minLength = field.getAttribute('minlength');
        const maxLength = field.getAttribute('maxlength');
        const pattern = field.getAttribute('pattern');
        
        let isValid = true;
        let errorMessage = '';
        
        // Required validation
        if (required && !value) {
            isValid = false;
            errorMessage = 'This field is required.';
        }
        
        // Length validation
        if (value && minLength && value.length < parseInt(minLength)) {
            isValid = false;
            errorMessage = `Minimum length is ${minLength} characters.`;
        }
        
        if (value && maxLength && value.length > parseInt(maxLength)) {
            isValid = false;
            errorMessage = `Maximum length is ${maxLength} characters.`;
        }
        
        // Pattern validation
        if (value && pattern) {
            const regex = new RegExp(pattern);
            if (!regex.test(value)) {
                isValid = false;
                errorMessage = 'Please enter a valid format.';
            }
        }
        
        // Type-specific validation
        if (value) {
            switch (type) {
                case 'email':
                    if (!this.isValidEmail(value)) {
                        isValid = false;
                        errorMessage = 'Please enter a valid email address.';
                    }
                    break;
                case 'tel':
                    if (!this.isValidPhone(value)) {
                        isValid = false;
                        errorMessage = 'Please enter a valid phone number.';
                    }
                    break;
                case 'number':
                    if (!this.isValidNumber(value)) {
                        isValid = false;
                        errorMessage = 'Please enter a valid number.';
                    }
                    break;
            }
        }
        
        // Custom validation based on field name
        if (value && field.name) {
            switch (field.name) {
                case 'aadhar':
                    if (!this.isValidAadhar(value)) {
                        isValid = false;
                        errorMessage = 'Please enter a valid Aadhar number (12 digits).';
                    }
                    break;
                case 'floor_no':
                    if (!this.isValidFloorNumber(value)) {
                        isValid = false;
                        errorMessage = 'Please enter a valid floor number.';
                    }
                    break;
                case 'door_no':
                    if (!this.isValidDoorNumber(value)) {
                        isValid = false;
                        errorMessage = 'Please enter a valid door number.';
                    }
                    break;
            }
        }
        
        this.showFieldValidation(field, isValid, errorMessage);
        return isValid;
    }
    
    validateForm(form) {
        const fields = form.querySelectorAll('.form-control');
        let allValid = true;
        
        fields.forEach(field => {
            if (!this.validateField(field)) {
                allValid = false;
            }
        });
        
        return allValid;
    }
    
    showFieldValidation(field, isValid, errorMessage) {
        // Remove existing validation classes and messages
        field.classList.remove('is-valid', 'is-invalid');
        const existingFeedback = field.parentNode.querySelector('.invalid-feedback');
        if (existingFeedback) {
            existingFeedback.remove();
        }
        
        if (field.value.trim()) {
            if (isValid) {
                field.classList.add('is-valid');
            } else {
                field.classList.add('is-invalid');
                
                // Add error message
                const feedback = document.createElement('div');
                feedback.className = 'invalid-feedback';
                feedback.textContent = errorMessage;
                field.parentNode.appendChild(feedback);
            }
        }
    }
    
    isValidEmail(email) {
        const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return regex.test(email);
    }
    
    isValidPhone(phone) {
        const regex = /^[\+]?[0-9]{10,15}$/;
        return regex.test(phone.replace(/\s/g, ''));
    }
    
    isValidNumber(number) {
        return !isNaN(number) && number.length > 0;
    }
    
    isValidAadhar(aadhar) {
        const regex = /^\d{12}$/;
        return regex.test(aadhar);
    }

    isValidFloorNumber(floor) {
        const num = parseInt(floor);
        return !isNaN(num) && num >= 0 && num <= 50;
    }
    
    isValidDoorNumber(door) {
        const num = parseInt(door);
        return !isNaN(num) && num >= 1 && num <= 1000;
    }
}

// Initialize Form Validator
const formValidator = new FormValidator();

// Additional utility functions
function formatAadharNumber(input) {
    let value = input.value.replace(/[^0-9]/g, '');
    
    // Format as 0000-0000-0000
    if (value.length > 4) {
        value = value.substring(0, 4) + '-' + value.substring(4);
    }
    if (value.length > 9) {
        value = value.substring(0, 9) + '-' + value.substring(9, 13);
    }
    
    input.value = value;
}

function formatPhoneNumber(input) {
    let value = input.value.replace(/[^0-9+]/g, '');
    
    // Simple formatting for Indian numbers
    if (value.length === 10) {
        value = value.replace(/(\d{5})(\d{5})/, '$1-$2');
    }
    
    input.value = value;
}

// Auto-format inputs
document.addEventListener('input', (e) => {
    const field = e.target;
    
    if (field.name === 'aadhar') {
        formatAadharNumber(field);
    } else if (field.type === 'tel') {
        formatPhoneNumber(field);
    }
});

// Form submission feedback
document.addEventListener('submit', (e) => {
    const form = e.target;
    const submitBtn = form.querySelector('button[type="submit"]');
    
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';
        
        // Re-enable button after 5 seconds (in case of errors)
        setTimeout(() => {
            submitBtn.disabled = false;
            submitBtn.innerHTML = submitBtn.getAttribute('data-original-text') || 'Submit';
        }, 5000);
    }
});

// Store original button text
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('button[type="submit"]').forEach(btn => {
        btn.setAttribute('data-original-text', btn.innerHTML);
    });
});
