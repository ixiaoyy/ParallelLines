<template>
  <div class="wrapper">
    <div class="item">
      <p class="title">
        {{ $t('项目说明') }}
      </p>
      <ul class="list">
        <li>项目提供<code>网页在线版</code>、<code>浏览器插件</code>、<code style="text-decoration: line-through;">桌面应用</code>等访问方式，具体参考<a :href="INTRODUCTION" target="_blank">中文文档</a></li>
        <li>
          项目基于
          <a :href="MIT" target="_blank">MIT</a> 协议开源 &copy; <a :href="AUTHOR_BLOG" target="_blank">Leon.D</a>，源码地址访问此处
          <a :href="GITHUB" target="_blank">Github</a>
        </li>
        <li>技术栈使用<code>Vite</code>、<code>Vue3</code>、<code>Typescript</code>, 欢迎各种PR贡献你的想法</li>
        <li>若对此项目有想法、建议或问题都可在Github的 <a :href="ISSUE" target="_blank">Issue</a> 上留言</li>
        <li>网站数据存储在浏览器本地的<code>LocalStorage</code>中，数据丢失无法进行恢复</li>
        <li>项目核心功能完全前端实现, 无需依赖后端。但部分物料组件依赖第三方在线API实现, 未必能保证稳定</li>
      </ul>
    </div>
    <div class="item">
      <p class="title">
        {{ $t('项目演示视频') }}
      </p>
      <a class="video-wrapper" :href="VIDEO" target="_blank">
        <img src="@/assets/imgs/video-thumb.png" alt="">
        <div class="mask">
          <Icon name="play-circle" size="1em" />
        </div>
      </a>
    </div>
  </div>
</template>

<script lang="ts" setup>
const MIT = 'https://github.com/leon-kfd/Dashboard/blob/main/LICENSE'
const AUTHOR_BLOG = 'https://kongfandong.cn'
const GITHUB = 'https://github.com/leon-kfd/Dashboard'
const ISSUE = 'https://github.com/leon-kfd/Dashboard/issues'
const VIDEO = 'https://www.bilibili.com/video/BV1Vu411Z7i1?share_source=copy_web'
const INTRODUCTION = 'https://doc.howdz.xyz'
</script>
<style lang="scss" scoped>
.wrapper {
  padding: 10px;
  padding-right: 20px;
  .item {
    margin-bottom: 20px;
  }
  .title {
    color: $color-grey1;
    margin-bottom: 8px;
    position: relative;
    font-weight: bold;
    display: inline-block;
    &:after {
      position: absolute;
      content: "";
      left: 0;
      width: 100%;
      bottom: 0;
      height: 8px;
      background: rgba(233, 174, 49, 0.2);
    }
  }
  .list {
    padding-left: 25px;
    li {
      color: $color-grey2;
      font-size: 14px;
      line-height: 1.5;
      position: relative;
      margin-bottom: 6px;
      &::before {
        position: absolute;
        left: -26px;
      }
      $emojis: '📙', '🌈', '🎉', '📧', '⚡', '💻';
      @each $e in $emojis {
        $i: index($emojis, $e);
        &:nth-child(#{$i}) {
          &::before {
            content: $e;
          }
        }
      }
      code {
        display: inline-block;
        padding: 0 2px;
        background: #fff2f2;
        border-radius: 2px;
        margin: 0 2px;
        font-size: 13px;
        font-weight: bold;
        font-family: inherit;
      }
      a {
        color: $color-primary;
        text-decoration: none;
        &:hover {
          color: $color-warning;
          text-decoration: underline;
        }
      }
    }
  }
  .video-wrapper {
    display: block;
    width: 100%;
    min-height: 120px;
    position: relative;
    img {
      width: 100%;
      height: auto;
    }
    .mask {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 48px;
      color: #fff;
      cursor: pointer;
      background: rgba(0,0,0,.4);
      backdrop-filter: blur(3px);
    }
  }
}
</style>
