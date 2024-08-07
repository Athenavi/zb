let newTab;

function prewXmind(xmind_url) {
    // 显示图像弹窗
    const imagePopup = document.getElementById('xmind-popup');
    imagePopup.style.display = 'block';
    continueXmind(xmind_url);
}

function continueXmind(xmind_url) {
    alert(xmind_url + "在新标签中打开");
    newTab = window.open(xmind_url, '_blank', 'xmind_prev');

    // 监听新标签页关闭事件
    window.addEventListener('beforeunload', function () {
        closeXmind();
    });
}

function closeXmind() {
    // 关闭图像弹窗
    const videoPopup = document.getElementById('xmind-popup');
    videoPopup.style.display = 'none';

    // 关闭特定ID的标签页
    if (newTab) {
        newTab.close();
    }
}
