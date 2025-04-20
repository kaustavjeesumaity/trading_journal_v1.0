document.addEventListener('DOMContentLoaded', function() {
    const platformSelect = document.getElementById('platformSelect');
    const accountSelect = document.getElementById('accountSelect');
    let currentAccount = null;

    // Load accounts when platform changes
    platformSelect.addEventListener('change', async function() {
        const platform = this.value;
        accountSelect.disabled = !platform;
        
        const response = await fetch(`/get-accounts/${platform}`);
        const accounts = await response.json();
        
        accountSelect.innerHTML = accounts.length 
            ? `<option value="">Select Account</option>` + 
              accounts.map(a => `<option value="${a.account_number}">${a.account_number}</option>`).join('')
            : `<option value="">No accounts found</option>`;
    });

    // Reload trades when account changes
    accountSelect.addEventListener('change', function() {
        currentAccount = this.value;
        window.location.href = `/?account=${currentAccount}`;
    });
});