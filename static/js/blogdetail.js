
    function loadPage(url, containerId) {
      var xhr = new XMLHttpRequest();
      xhr.open('GET', url, true);

      xhr.onload = function () {
        if (xhr.status === 200) {
          var tempDiv = document.createElement('div');
          tempDiv.innerHTML = xhr.responseText;

          var newCommentsContainer = tempDiv.querySelector('#' + containerId);
          var currentCommentsContainer = document.getElementById(containerId);

          if (newCommentsContainer && currentCommentsContainer) {
            currentCommentsContainer.innerHTML = newCommentsContainer.innerHTML;
          }
        }
      };

      xhr.send();
    }

  // 检测设备类型
  var isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);

  // 根据设备类型添加样式
  if (isMobile) {
    document.addEventListener("DOMContentLoaded", function() {
      var showOnDesktopDiv = document.querySelector(".show-on-desktop");
      if (showOnDesktopDiv) {
        showOnDesktopDiv.style.display = "none";
      }
    });
  }

    function toggleSidebar() {
  var sidebar = document.getElementById("sidebar");
  if (sidebar.style.display === "none") {
    sidebar.style.display = "block";
  } else {
    sidebar.style.display = "none";
  }
}
var pageContent = document.body.innerText;
// 检测是否包含作者单词
if (pageContent.includes("author")) {
  // 创建一个新的button元素
  var button = document.createElement("button");
  button.setAttribute("onclick", "toggleSidebar()");
  button.innerText = "显示/隐藏侧边栏";

  // 将按钮添加到<div id="SideList"></div>之间
  var sideList = document.getElementById("SideList");
  sideList.insertBefore(button, sideList.firstChild);
}

    if (window !== window.top) {
  // 当前窗口被嵌套在另一个iframe中
  alert('当前视图会影响您的体验！！！\n请点击搜索结果后的小图标进行访问');
  window.location.href = '/search';
}


// 使用 JavaScript 代码实现
var sidebar = document.getElementById('sidebar');
var initialX = null;

sidebar.addEventListener('mousedown', function(event) {
  event.preventDefault();
  initialX = event.clientX;
  document.addEventListener('mousemove', moveElement);

  document.addEventListener('mouseup', function() {
    document.removeEventListener('mousemove', moveElement);
    initialX = null;
  });

  function moveElement(event) {
    var deltaX = event.clientX - initialX;
    var newX = sidebar.offsetLeft + deltaX;
    sidebar.style.left = newX + 'px';
    initialX = event.clientX;
  }
});

// 使用 jQuery 实现
$('#sidebar').draggable({
  axis: 'x'  // 限制只能在水平方向拖动
});