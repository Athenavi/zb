function submitForm(article) {
    var passwordInput = document.getElementById("password");
    var password = passwordInput.value;

    var xhr = new XMLHttpRequest();
    xhr.open("POST", "/blog/" + article, true);
    xhr.setRequestHeader("Content-type", "application/json");

    var data = JSON.stringify({
        "article": article,
        "code": password
    });

    xhr.onreadystatechange = function () {
        if (xhr.readyState === XMLHttpRequest.DONE) {
            if (xhr.status === 200) {
                alert("提交成功！");   // 请求成功的处理逻辑
            } else {
                alert("提交失败。请稍后再试。");   // 请求失败的处理逻辑
            }
        }
    };

    xhr.send(data);
}

window.onload = function () {
    document.getElementById("password").focus();
};