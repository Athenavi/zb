// 保存音乐列表信息
var musicList = [];
// 声明变量，保存当前播放的是哪一首歌曲
var currentIndex = 0;

// 1. 加载音乐列表信息
$.ajax({
    type: "GET",
    url: "/static/music/music.json",
    dataType: "json",
    credentials: 'include',
    success: function (data) {
        musicList = data;
        render(musicList[currentIndex]);
        renderMusicList(musicList);
    },
});

// 给播放按钮绑定点击事件
$("#playBtn").on("click", function () {
    if ($("audio").get(0).paused) {
        // 暂停状态，应该播放
        // 修改播放按钮的图标状态
        $(this).removeClass("fa-play").addClass("fa-pause");
        // 让音乐信息卡片显示出来
        $(".player-info").addClass("highlight");
        // 让封面旋转起来
        $(".cover").css({
            "animation-play-state": "running",
        });

        // 让音乐播放起来
        $("audio").get(0).play();
    } else {
        // 播放状态，应该暂停
        $(this).removeClass("fa-pause").addClass("fa-play");
        // 让音乐信息卡片消失
        $(".player-info").removeClass("highlight");
        // 让封面旋转暂停
        $(".cover").css({
            "animation-play-state": "paused",
        });

        // 让音乐暂停
        $("audio").get(0).pause();
    }

    // 重新渲染列表数据
    renderMusicList(musicList);
});

// 给上一首按钮绑定点击事件
$("#prevBtn").on("click", function () {
    if (currentIndex > 0) {
        currentIndex--;
    } else {
        currentIndex = musicList.length - 1;
    }

    // 重新渲染歌曲信息
    render(musicList[currentIndex]);
    // 让音乐播放
    $("#playBtn").trigger("click");
});

// 给下一首按钮绑定点击事件
$("#nextBtn").on("click", function () {
    if (currentIndex < musicList.length - 1) {
        currentIndex++;
    } else {
        currentIndex = 0;
    }
    // 重新渲染歌曲信息
    render(musicList[currentIndex]);
    // 让音乐播放
    $("#playBtn").trigger("click");
});

// 给音乐列表绑定点击事件
$("#openModal").on("click", function () {
    $(".modal").css({
        display: "block",
    });
});

$(".modal-close").on("click", function () {
    $(".modal").css({
        display: "none",
    });
});

// 监听audio标签的 timeupdate 事件
$("audio").on("timeupdate", function () {
    // 获取音乐当前到的时间，单位：秒
    var currentTime = $("audio").get(0).currentTime || 0;
    // 获取音乐的总时长，单位：秒
    var duration = $("audio").get(0).duration || 0;
    // 设置当前播放时间
    $(".current-time").text(formatTime(currentTime));
    // 设置进度条
    var value = (currentTime / duration) * 100;
    $(".music_progress_line").css({
        width: value + "%",
    });
});

// 监听音乐播放完毕的事件
$("audio").on("ended", function () {
    $("#playBtn").removeClass("fa-pause").addClass("fa-play");
    // 让封面旋转暂停
    $(".cover").css({
        "animation-play-state": "paused",
    });
});

// 通过事件委托给音乐列表的播放按钮绑定点击事件
$(".music-list").on("click", ".play-circle", function () {
    if ($(this).hasClass("fa-play-circle")) {
        var index = $(this).attr("data-index");
        currentIndex = index;
        render(musicList[currentIndex]);
        $("#playBtn").trigger("click");
    } else {
        $("#playBtn").trigger("click");
    }
});

// 格式化时间
function formatTime(time) {
    // 329 -> 05:29
    var min = parseInt(time / 60);
    var sec = parseInt(time % 60);
    min = min < 10 ? "0" + min : min;
    sec = sec < 10 ? "0" + sec : sec;

    return `${min}:${sec}`;
}

// 根据信息，设置页面对应标签中的内容
function render(data) {
    $(".name").text(data.name);
    $(".singer-album").text(`${data.singer} - ${data.album}`);
    $(".time").text(data.time);
    $(".cover img").attr("src", data.cover);
    $("audio").attr("src", data.audio_url);
    $(".mask_bg").css({
        background: `url("${data.cover}") no-repeat center center`,
    });
}

// 根据音乐列表数据，创建li
function renderMusicList(list) {
    $(".music-list").empty();

    $.each(list, function (index, item) {
        var $li = $(`
      <li class="${index == currentIndex ? "playing" : ""}">
        <span>0${index + 1}. ${item.name} - ${item.singer}</span>
        <span data-index="${index}" class="fa ${
            index == currentIndex && !$("audio").get(0).paused
                ? "fa-pause-circle"
                : "fa-play-circle"
        } play-circle"></span>
      </li>
    `);
        $(".music-list").append($li);
    });
}
