var docsifyDemo=function(s){"use strict";function b(e){return w(e)||g(e)||h(e)||x()}function w(e){if(Array.isArray(e))return m(e)}function g(e){if(typeof Symbol!="undefined"&&e[Symbol.iterator]!=null||e["@@iterator"]!=null)return Array.from(e)}function h(e,n){if(!!e){if(typeof e=="string")return m(e,n);var t=Object.prototype.toString.call(e).slice(8,-1);if(t==="Object"&&e.constructor&&(t=e.constructor.name),t==="Map"||t==="Set")return Array.from(e);if(t==="Arguments"||/^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(t))return m(e,n)}}function m(e,n){(n==null||n>e.length)&&(n=e.length);for(var t=0,i=new Array(n);t<n;t++)i[t]=e[t];return i}function x(){throw new TypeError(`Invalid attempt to spread non-iterable instance.
In order to be iterable, non-array objects must have a [Symbol.iterator]() method.`)}function A(e,n){var t=typeof Symbol!="undefined"&&e[Symbol.iterator]||e["@@iterator"];if(!t){if(Array.isArray(e)||(t=h(e))||n&&e&&typeof e.length=="number"){t&&(e=t);var i=0,o=function(){};return{s:o,n:function(){return i>=e.length?{done:!0}:{done:!1,value:e[i++]}},e:function(d){throw d},f:o}}throw new TypeError(`Invalid attempt to iterate non-iterable instance.
In order to be iterable, non-array objects must have a [Symbol.iterator]() method.`)}var c=!0,r=!1,l;return{s:function(){t=t.call(e)},n:function(){var d=t.next();return c=d.done,d},e:function(d){r=!0,l=d},f:function(){try{!c&&t.return!=null&&t.return()}finally{if(r)throw l}}}}function S(e,n,t){for(var i=document.getElementsByTagName(n),o=!1,c=0;c<i.length;c++)if(i[c].getAttribute("href")===e||i[c].getAttribute("src")===e){o=!0;break}if(o)t&&t();else{var r;n==="script"?(r=document.createElement("script"),r.type="text/javascript",r.src=e):n==="link"&&(r=document.createElement("link"),r.rel="stylesheet",r.type="text/css",r.href=e),r.readyState?r.onreadystatechange=function(){(r.readyState==="loaded"||r.readyState==="complete")&&(r.onreadystatechange=null,t&&t())}:r.onload=function(){t&&t()},document.head.appendChild(r)}}function p(e,n){var t=0;function i(o){S("https://xmindltd.github.io/xmind-embed-viewer/xmind-embed-viewer.js","script",o)}i(),e.afterEach(function(o,c){var r=new DOMParser,l=r.parseFromString(o,"text/html"),d=l.querySelectorAll("pre"),y=b(d);y.forEach(function(u){var v="xmind_box_"+t;if(u.getAttribute("data-lang")=="xmind preview"){var f=u.innerText;console.info("link:"+f),u.outerHTML;var a=document.createElement("div");a.innerHTML=`
                        <div class="xmind" id="`.concat(v,`" >
                            <div class="xmind_preview" data-href="`).concat(f,`">
                                <div class="loading-xmind-overlay">
                                    <svg t="1703331194570" class="icon" viewBox="0 0 1124 1124" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="4276" width="70" height="70">
                                        <path d="M876.864 782.592c3.264 0 6.272-3.2 6.272-6.656 0-3.456-3.008-6.592-6.272-6.592-3.264 0-6.272 3.2-6.272 6.592 0 3.456 3.008 6.656 6.272 6.656z m-140.544 153.344c2.304 2.432 5.568 3.84 8.768 3.84a12.16 12.16 0 0 0 8.832-3.84 13.76 13.76 0 0 0 0-18.56 12.224 12.224 0 0 0-8.832-3.84 12.16 12.16 0 0 0-8.768 3.84 13.696 13.696 0 0 0 0 18.56zM552.32 1018.24c3.456 3.648 8.32 5.76 13.184 5.76a18.368 18.368 0 0 0 13.184-5.76 20.608 20.608 0 0 0 0-27.968 18.368 18.368 0 0 0-13.184-5.824 18.368 18.368 0 0 0-13.184 5.76 20.608 20.608 0 0 0 0 28.032z m-198.336-5.76c4.608 4.8 11.072 7.68 17.6 7.68a24.448 24.448 0 0 0 17.536-7.68 27.456 27.456 0 0 0 0-37.248 24.448 24.448 0 0 0-17.536-7.68 24.448 24.448 0 0 0-17.6 7.68 27.52 27.52 0 0 0 0 37.184z m-175.68-91.84c5.76 6.08 13.824 9.6 21.952 9.6a30.592 30.592 0 0 0 22.016-9.6 34.368 34.368 0 0 0 0-46.592 30.592 30.592 0 0 0-22.016-9.6 30.592 30.592 0 0 0-21.952 9.6 34.368 34.368 0 0 0 0 46.592z m-121.152-159.36c6.912 7.36 16.64 11.648 26.368 11.648a36.736 36.736 0 0 0 26.432-11.584 41.28 41.28 0 0 0 0-55.936 36.736 36.736 0 0 0-26.432-11.584 36.8 36.8 0 0 0-26.368 11.52 41.28 41.28 0 0 0 0 56zM12.736 564.672a42.88 42.88 0 0 0 30.784 13.44 42.88 42.88 0 0 0 30.784-13.44 48.128 48.128 0 0 0 0-65.216 42.88 42.88 0 0 0-30.72-13.44 42.88 42.88 0 0 0-30.848 13.44 48.128 48.128 0 0 0 0 65.216z m39.808-195.392a48.96 48.96 0 0 0 35.2 15.36 48.96 48.96 0 0 0 35.2-15.36 54.976 54.976 0 0 0 0-74.56 48.96 48.96 0 0 0-35.2-15.424 48.96 48.96 0 0 0-35.2 15.424 54.976 54.976 0 0 0 0 74.56zM168.32 212.48c10.368 11.008 24.96 17.408 39.68 17.408 14.592 0 29.184-6.4 39.552-17.408a61.888 61.888 0 0 0 0-83.84 55.104 55.104 0 0 0-39.616-17.408c-14.656 0-29.248 6.4-39.616 17.408a61.888 61.888 0 0 0 0 83.84zM337.344 124.8c11.52 12.16 27.712 19.264 43.968 19.264 16.256 0 32.448-7.04 43.968-19.264a68.672 68.672 0 0 0 0-93.184 61.248 61.248 0 0 0-43.968-19.264 61.248 61.248 0 0 0-43.968 19.264 68.736 68.736 0 0 0 0 93.184z m189.632-1.088c12.672 13.44 30.528 21.248 48.448 21.248s35.712-7.808 48.384-21.248a75.584 75.584 0 0 0 0-102.464A67.392 67.392 0 0 0 575.36 0c-17.92 0-35.776 7.808-48.448 21.248a75.584 75.584 0 0 0 0 102.464z m173.824 86.592c13.824 14.592 33.28 23.104 52.736 23.104 19.584 0 39.04-8.512 52.8-23.104a82.432 82.432 0 0 0 0-111.744 73.472 73.472 0 0 0-52.8-23.168c-19.52 0-38.912 8.512-52.736 23.168a82.432 82.432 0 0 0 0 111.744z m124.032 158.528c14.976 15.872 36.032 25.088 57.216 25.088 21.12 0 42.24-9.216 57.152-25.088a89.344 89.344 0 0 0 0-121.088 79.616 79.616 0 0 0-57.152-25.088c-21.184 0-42.24 9.216-57.216 25.088a89.344 89.344 0 0 0 0 121.088z m50.432 204.032c16.128 17.088 38.784 27.008 61.632 27.008 22.784 0 45.44-9.92 61.568-27.008a96.256 96.256 0 0 0 0-130.432 85.76 85.76 0 0 0-61.568-27.072c-22.848 0-45.44 9.984-61.632 27.072a96.192 96.192 0 0 0 0 130.432z" fill="#262626" p-id="4277">
                                            <animateTransform attributeName="transform" type="rotate" from="0 562 562" to="360 562 562" dur="2s" repeatCount="indefinite"/>
                                        </path>
                                        <text x="260" y="640" style="font:italic 220px serif">Xmind</text>
                                    </svg>
                                </div>
                            </div>
                            <div class="demo_code" >
                                `).concat(f,`
                            </div>
                        </div>
                    `).trim(),a=a.firstChild,u.replaceWith(a)}t++}),c(l.body.innerHTML)}),e.doneEach(function(){var o=function c(){if(window.XMindEmbedViewer){var r=document.querySelectorAll(".xmind_preview"),l=A(r),d;try{var y=function(){var u=d.value,v=u.getAttribute("data-href"),f=new XMindEmbedViewer({el:u,region:"cn",style:{height:"888px"}});f.addEventListener("sheets-load",function(){var a=document.querySelector(".loading-xmind-overlay");a&&a.parentNode.removeChild(a)}),fetch(v).then(function(a){return a.arrayBuffer()}).then(function(a){return f.load(a)})};for(l.s();!(d=l.n()).done;)y()}catch(u){l.e(u)}finally{l.f()}}else setTimeout(c,1e3)};i(o)})}if(window.$docsify)window.$docsify.plugins=[].concat(p,window.$docsify.plugins||[]);else throw new Error("Docsify is not loaded");return s.docsifyXmind=p,Object.defineProperty(s,"__esModule",{value:!0}),s}({});
//# sourceMappingURL=index.min.js.map
