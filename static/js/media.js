function showImage(img) {
    fetch('/media', {
        method: 'POST',
        credentials: 'include',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({img_name: img})
    })
        .then(response => response.blob())
        .then(blob => {
            const imageURL = URL.createObjectURL(blob);
            document.getElementById('popup-image').src = imageURL;
            document.getElementById('image-popup').style.display = 'block';
        })
        .catch(error => console.error(error));
}

function closeImage() {
    document.getElementById('image-popup').style.display = 'none';
}

function closeVideo() {
    document.getElementById("video-image").src = ""; // 清空视频源
    document.getElementById("video-popup").classList.add("hidden"); // 隐藏弹窗
}

document.addEventListener('DOMContentLoaded', function () {
    const h3Elements = document.querySelectorAll('.card-title');

    h3Elements.forEach(element => {
        if (element.textContent.trim().length > 12) {
            const h6Element = document.createElement('h6');
            h6Element.innerHTML = element.innerHTML;
            element.parentNode.replaceChild(h6Element, element);
        }
    });
});

async function deleteFile(filename) {
    // 询问用户确认
    const isConfirmed = confirm(`您确定要删除 ${filename} 吗？`);

    if (!isConfirmed) {
        alert('取消删除操作。');
        return; // 如果用户选择否，则退出函数
    }

    try {
        const response = await fetch(`/api/delete/${filename}`, {
            method: 'DELETE',
            credentials: 'include',
        });

        if (response.ok) {
            const result = await response.json();
            console.log('File deleted successfully:', result);
            alert(filename + ' 删除成功！');
        } else {
            console.error('Error deleting file:', response.statusText);
            alert(filename + ' 失败！错误信息:' + response.statusText);
        }
    } catch (error) {
        console.error('请求失败:', error);
    }
}


function setPreference(preference) {
    document.cookie = `preference=${preference}; path=/; max-age=604800`;
    document.getElementById('preferenceDiv').style.display = 'none';
    document.getElementById('overlay').style.display = 'none';
    window.location.reload();
}

function getCookie(cname) {
    const name = cname + "=";
    const decodedCookie = decodeURIComponent(document.cookie);
    const ca = decodedCookie.split(';');
    for (let i = 0; i < ca.length; i++) {
        let c = ca[i];
        while (c.charAt(0) === ' ') {
            c = c.substring(1);
        }
        if (c.indexOf(name) === 0) {
            return c.substring(name.length, c.length);
        }
    }
    return "";
}

window.onload = function () {
    const preference = getCookie("preference");
    if (!preference) {
        document.getElementById('preferenceDiv').style.display = 'block';
        document.getElementById('overlay').style.display = 'block';
    }
};