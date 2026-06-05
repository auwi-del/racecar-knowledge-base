**<font style="background-color:#FBDE28;">本组现在至少有两名开发人员（洋溢，wangxingli，所以开发必须遵守本文档规范)</font>**

# 一个新电脑, 如何获取最新的整套仓库?
注意，如果你克隆过一次了，那你不用次次都克隆，你本地有了，就能用了



1. 打开一个空vscode 窗口（新建的）
2. 点击左侧侧边栏中的 git，点击克隆仓库

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/54164956/1780627225575-1cb056b8-5d93-4b5d-a4a3-dafb9417cabd.png)



粘贴从github 咱们组仓库中获取到的连接（.git 结尾)

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/54164956/1780624996771-cd9ebf09-b521-4edf-b5c4-12c1fc480f53.png)



粘贴到 code 的弹窗中。

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/54164956/1780625077841-89212f3e-9821-4d68-b93b-477ed56d9314.png)





随后， code 提示，问你“你要将仓库下载到哪里？”

你一律选默认位置即可

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/54164956/1780625113387-ac588303-0506-4ea6-93e5-b466bc4ed5cd.png)







几秒钟后，就能打开最新的云端版本

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/54164956/1780625176518-fd58ea93-fbfb-4883-be03-f17d22a817d1.png)



# 做了更改，如何提交？
假如你做了如下修改：

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/54164956/1780625848852-95f0a3b9-16ac-42e6-a7a3-ff1f49a2b183.png)



## 第一步， 做一遍像正常的 “本地”git仓库的提交
<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/54164956/1780625966843-36445d6c-3d5e-4913-867c-d70a0196deee.png)



## 观察提交后的情况
从图片中可知：本地进行了一次提交后，本地比云端新。

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/54164956/1780626027784-566d5289-9822-4b51-8578-7e96896913f4.png)



## 每天下班后，或者中午吃饭，将你的更改提交到云端（确保挂了梯子）：
<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/54164956/1780626093616-8ea045bd-9c4c-4809-a7d6-2c5d074467ad.png)



至于这个，仅在第一次提交的时候需要登录一下github，仅需点击浏览器登录即可

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/54164956/1780626127635-2a254257-43ab-4e2a-b216-2ebce9b947f4.png)



<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/54164956/1780626194952-2ecf129c-305b-4c29-b532-8665842ea429.png)



## 在浏览器中查看
<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/54164956/1780626252544-e97b2461-46e7-434f-8c66-58eda10607f2.png)



## 那你的队友那边显示啥？
<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/54164956/1780626427231-f9b106b6-6f12-4eef-9088-61401a41b048.png)







<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/54164956/1780626438819-d0c0adc3-46c2-4c4e-9176-37171c6971d0.png)



# GIT 术语
**本地仓库			就是你项目目录中的 .git/**

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/54164956/1780627564768-39a58cd8-5358-4eca-9974-576d79122cd4.png)



云端仓库			就是你的github中看到的

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/54164956/1780627702360-ffe8696b-a9a2-4bfb-9be3-0b8f445fb6fa.png)





commit 提交，将这次修改的文件管理存档到本地仓库

push	推送		将本地仓库更新到云端

pull		拉取		将云端仓库更新到本地







# git是如何应对冲突的？
如果你和队友都基于一个版本进行修改，

每个人写了一个文件，就必然产生冲突

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/54164956/1780626799412-d16b5a08-5529-4f56-be52-b990ba64a442.png)



而假设你的队友洋溢，增加了如下文件：

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/32508923/1780626871997-d714ef91-3e2b-46a2-9788-252396a3af4b.png)



并且他抢先一步，提交到了云端

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/32508923/1780626966222-514f5302-c392-4f55-90e7-56681b8d8b38.png)





而这时候，wangxingli 再提交，会发生什么？

**会看到冲突视图**

**强烈建议大家仔细理解这张图：**

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/54164956/1780627040395-29ed5a5f-8d08-40b5-916c-454759507d71.png)



<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/54164956/1780627136764-c339de67-e6ff-4e9d-adf7-b0d5a83547ff.png)

> # GIT 牛逼

做完这一波操作之后，两个人的两台电脑上，都能看见这两个文件

真是太牛逼了



<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/54164956/1780627450839-2c338f6b-5365-47f4-a4ac-81c747f1d684.png)

# 以后怎么启动本地电脑上的Claude？
1. 直接cd race [按键盘上的tab]， 自动补全成目录
2. 输入claude



**否则，skill，全部功能都将失效**

****

**本组现在至少有两名开发人员（洋溢，wangxingli，所以开发必须遵守本文档规范)**

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/54164956/1780625399912-4468dec2-dc39-4f99-b79c-b568b5670124.png)



只要进入到本组仓库所在的目录，

就会发现，skill全部生效，全部好使



<font style="background-color:#FBDE28;">注意：</font>**<font style="background-color:#FBDE28;">claude 原先的全局 skill 均更改为项目级skill</font>**

<!-- 这是一张图片，ocr 内容为： -->
![](https://cdn.nlark.com/yuque/0/2026/png/54164956/1780625521724-b5b254c3-0409-41d8-a493-2bfba3a599f1.png)







# 更改的内容
运行 csv-manager，下载的点位会自动放在：`**C:\Users\LX\racecar-knowledge-base\点位管理器**`



