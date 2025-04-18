document.addEventListener('DOMContentLoaded', function() {
    const ctx = document.getElementById('pnlChart').getContext('2d');
    
    fetch('/chart-data')
        .then(response => response.json())
        .then(data => {
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.dates,
                    datasets: [{
                        label: 'Cumulative Net P&L',
                        data: data.cumulative_pnl,
                        borderColor: '#4CAF50',
                        backgroundColor: 'rgba(76, 175, 80, 0.2)',
                        borderWidth: 2,
                        pointRadius: 3,
                        tension: 0.1
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: {
                            position: 'top',
                        },
                        title: {
                            display: true,
                            text: 'Cumulative Profit & Loss'
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            title: {
                                display: true,
                                text: 'Net P&L'
                            }
                        }
                    }
                }
            });
        });
});