const fetchIpInfo = () => {
    fetch('/api/ip')
        .then(response => {
            // Ensure response is OK and parse JSON
            if (response.ok) {
                return response.json(); // Change from response.data to response.json()
            }
            return Promise.reject('Network response was not ok');
        })
        .then(data => {
            showWelcome(data.ip); // Adjust to access ip from the object
            hideLoadingSpinner();  // Hide loading spinner after data is received
        })
        .catch(() => {
            showErrorMessage();
            hideLoadingSpinner();  // Hide loading spinner on error
        });
};

const showWelcome = (ipLocationData) => {
    if (!ipLocationData) {
        return showErrorMessage();
    }
    const welcomeInfoElement = document.getElementById("welcome-info");
    welcomeInfoElement.style.display = 'block';
    welcomeInfoElement.innerHTML = `
            💖 欢迎IP <b><span style="color:#3390ff;">${ipLocationData}</span></b> 的朋友<br>
        `;
};

const showErrorMessage = () => {
    const welcomeInfoElement = document.getElementById("welcome-info");
    welcomeInfoElement.style.display = 'block';
    welcomeInfoElement.innerHTML = `<p>获取IP信息失败,请检查网络.</p>`;
};

const hideLoadingSpinner = () => {
    const loadingSpinner = document.querySelector('.loading-spinner');
    if (loadingSpinner) {
        loadingSpinner.style.display = 'none';
    }
};

const initialize = () => {
    fetchIpInfo();
};

window.onload = initialize;