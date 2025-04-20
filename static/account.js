async function loadAccounts(platform) {
    try {
        const response = await fetch(`/get-accounts/${platform}`);
        const accounts = await response.json();
        
        accountSelect.innerHTML = accounts.length 
            ? `<option value="">Select Account</option>` + 
              accounts.map(a => `<option value="${a.account_number}">${a.account_number}</option>`).join('')
            : `<option value="">No accounts found</option>`;
        
        accountSelect.disabled = !platform;
    } catch (error) {
        console.error('Account loading failed:', error);
    }
}