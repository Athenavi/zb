const fetchIpInfo = () => {
    // 获取当前 URL
    const currentUrl = window.location.href;
    const url = new URL(currentUrl);
    const params = new URLSearchParams(url.search);
    const apiUrl = '/api/ip?' + params.toString();
    fetch(apiUrl, {
        method: 'GET', // 或者 'POST' 等方法
        credentials: 'include' // 发送请求时包含 Cookie
    })
        .then(response => {
            if (response.ok) {
                return response.json();
            }
            return Promise.reject('Network response was not ok');
        })
        .then(data => {
            showWelcome(data.ip);
            hideLoadingSpinner();
        })
        .catch(() => {
            showErrorMessage();
            hideLoadingSpinner();
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