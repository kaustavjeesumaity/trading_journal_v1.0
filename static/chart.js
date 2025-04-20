document.addEventListener('DOMContentLoaded', function() {
    const ctx = document.getElementById('pnlChart');
    
    if (!ctx) return;
    
    const params = new URLSearchParams(window.location.search);
    const platform = params.get('platform');
    const account = params.get('account');
    console.log('Platform:', platform, 'Account:', account);
    if (!platform || !account) {
        console.log('No filter selected - skipping chart');
        return;
    }
    
    fetch(`/chart-data?platform=${platform}&account=${account}`)
        .then(response => response.json())
        .then(data => {
            console.log('Chart data:', data);
            new Chart(ctx, {
                type: 'line',
                data: data,
                options: {
                    responsive: true,
                    plugins: {
                        legend: { position: 'top' },
                        title: {
                            display: true,
                            text: 'Cumulative P&L Trend'
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: { display: true, text: 'Net P&L' }
                        }
                    }
                }
            });
        })
        .catch(error => console.error('Chart error:', error));
});