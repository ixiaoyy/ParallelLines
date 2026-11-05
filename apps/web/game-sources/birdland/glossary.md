# 《BIRDLAND》汉化标准术语表与语法规范

## 一、Twine Snowman 语法保护铁律（绝对不可破坏）

1. **JSON 结构保持不变**：
   - 每个元素包含 `pid`, `name`, `tags`, `position`, `body` 五个字段。
   - **只能修改 `body` 字段中的可见文本**，`pid`, `name`, `tags`, `position` 必须原样保留！
2. **EJS / JavaScript 脚本块 `<% ... %>` 与 `<%= ... %>`**：
   - 变量名与函数调用名不可修改，例如 `<% s.tenacityup += 1; s.west2 = true %>`、`<%= display("west5") %>`、`<% setmorning() %>`、`<% autosave() %>`。
   - **属性检定函数**：
     - `serenitylink("中文选项文本", "target_name", 3)`
     - `alacritylink("中文选项文本", "target_name", 3)`
     - `tenacitylink("中文选项文本", "target_name", 3)`
     - `vigilancelink("中文选项文本", "target_name", 3)`
     - `melancholylink("中文选项文本", "target_name", 3)`
     - `guilelink("中文选项文本", "target_name", 3)`
     - **注意**：只翻译第 1 个参数（显示文本），第 2 个参数（跳转节点名）和第 3 个参数（数值）绝对不能改！注意引号转义（若内部无双引号直接用中文文本即可）。
3. **Twine 链接语法（两种格式务必看清方向！）**：
   - **格式 A：`[[target_name<-中文选项文本]]`**：箭头 `<-` **左侧是目标节点 ID（严禁修改！）**，**右侧是显示文字（翻译右侧！）**。
     - 例如：`* [[west2<-To keep the law.]]` 翻译为 `* [[west2<-维护法律。]]`
     - 例如：`* [[olympics-end<-Next →]]` 翻译为 `* [[olympics-end<-继续 →]]`
   - **格式 B：`[[中文选项文本|target_name]]`**：竖线 `|` **左侧是显示文字（翻译左侧！）**，**右侧是目标节点 ID（严禁修改！）**。
     - 例如：`* [[What's being a detective like?|bell5]]` 翻译为 `* [[当侦探是什么感觉？|bell5]]`
4. **延时样式块 `[ ... ]{.delay1s}`**：
   - 保留 `[` 和 `]{.delay1s}` 标记。

---

## 二、发言人（Speaker）标准译名表

对白行开头的 `SPEAKER:` 统一使用**中文角色名 + 中文全角冒号 `：`**（或者跟随原版格式 `角色名：`）：

| 英文前缀 | 标准中文前缀 | 备注 |
| :--- | :--- | :--- |
| `YOU:` | `你：` | 主角布里奇特（Bridget Leaside） |
| `BELL:` | `贝尔：` | Bellwoods "Bell" W. Park（贝尔·帕克，中间名 Wether“阉羊/领头羊”） |
| `MACKENZIE:` | `麦肯齐：` | Mackenzie Singh（麦肯齐·辛格） |
| `LIZ:` | `莉兹：` | Elizabeth "Liz" Wei（伊丽莎白·“莉兹”·魏） |
| `TAYLOR M:` | `泰勒·M：` | Taylor Massey（泰勒·马西） |
| `TAYLOR C:` | `泰勒·C：` | Taylor Creek（泰勒·克里克） |
| `ZOE:` | `佐伊：` | Zoe Price（佐伊·普莱斯） |
| `ALISHA SAIL:` | `艾莉莎·扬帆：` | Alisha "Sail" Avi（艾莉莎·“扬帆”·阿维，帆船辅导员） |
| `DAN CANOE:` | `丹·独木舟：` | Dan "Canoe" Landing（丹·“独木舟”·兰丁，独木舟辅导员） |
| `TJ SWIM:` | `TJ·游泳：` | TJ "Swim" Phillips（TJ·“游泳”·菲利普斯，游泳辅导员） |
| `CASSIDY WOODS:` | `卡西迪·森林：` | Cassidy "Woods" Warden（卡西迪·“森林”·沃登，自然辅导员） |
| `HEATHER ROPES:` | `海瑟·绳索：` | Heather "Ropes" Balão（海瑟·“绳索”·巴劳，绳索辅导员） |
| `LOGAN CRAFTS:` | `洛根·手工：` | Logan "Crafts" Dinowitz（洛根·“手工”·迪诺维茨，美术手工辅导员） |
| `NATHAN:` | `内森：` | 讨人嫌的男营员 |
| `CLEMENTINE CREEVY:` | `克莱门汀·克里维：` | 萨蒂（Sadie）起的假名，真名 Sadie（萨蒂） |
| `KEVIN:` | `凯文：` | 男营员 |
| `DEPUTY:` | `副警长：` | 第1夜西部梦境 |
| `TOWN DRUNK:` | `镇上的酒鬼：` | 第1夜西部梦境 |
| `BARKEEP:` | `酒保：` | 第1夜西部梦境 |
| `FIRST MATE:` | `大副：` | 第2夜海盗梦境 |
| `SAILOR:` | `水手：` | 第2夜海盗梦境 |
| `CREW:` | `船员们：` | 第2夜海盗梦境 |
| `RIVAL PIRATE #1:` | `死对头海盗 #1：` | 第2夜海盗梦境 |
| `RIVAL PIRATE #2:` | `死对头海盗 #2：` | 第2夜海盗梦境 |
| `COACH:` | `教练：` | 第3夜曲棍球梦境 |
| `REFEREE:` | `裁判：` | 第3夜曲棍球梦境 |
| `OPPOSING PLAYER:` | `对方球员：` | 第3夜曲棍球梦境 |
| `ANNOUNCER:` | `解说员：` | 第3夜曲棍球梦境 |
| `CROWD:` | `观众群：` | 第3夜曲棍球梦境 |
| `SPECTATOR #1`~`#4:` | `观众 #1`~`#4：` | 第3夜曲棍球梦境 |
| `MANAGER:` | `经纪人：` | 第4夜音乐人梦境 |
| `STAGE MANAGER:` | `舞台监督：` | 第4夜音乐人梦境 |
| `AUDIENCE:` | `台下观众：` | 第4夜音乐人梦境 |
| `ASSISTANT:` | `助手：` | 第5夜侦探梦境 |
| `BUTLER:` | `管家：` | 第5夜侦探梦境 |
| `COLONEL:` | `上校：` | 第5夜侦探梦境 |
| `DUCHESS:` | `公爵夫人：` | 第5夜侦探梦境 |
| `LAYABOUT:` / `LAYABOUT SON:` | `二流子：` / `二流子少爷：` | 第5夜侦探梦境 |
| `FORTUNE TELLER:` | `占卜师：` | 第5夜侦探梦境 |
| `VICITM:` | `受害者：` | 第5夜侦探梦境（原文拼写为 VICITM） |
| `ALL SUSPECTS:` | `全体嫌疑人：` | 第5夜侦探梦境 |
| `FELLOW STUDENT:` / `FOLLOW STUDENT:` | `同学：` | 第6夜大学梦境 |
| `ANOTHER STUDENT:` | `另一名学生：` | 第6夜大学梦境 |
| `PROFESSOR:` | `教授：` | 第6夜大学梦境 |
| `EVERYONE IN CLASS:` | `全班同学：` | 第6夜大学梦境 |
| `PARTYGOER:` | `派对宾客：` | 第6夜大学梦境 |
| `BRO #1:` / `BRO #2:` | `兄弟会男生 #1：` / `兄弟会男生 #2：` | 第6夜大学梦境 |
| `FRISBEE PLAYER #1:` / `#2:` | `飞盘手 #1：` / `飞盘手 #2：` | 第6夜大学梦境 |
| `BIRD:` | `鸟人：` | 鸟人 |
| `BIRD-SHAPED FIGURE:` | `鸟形身影：` | 鸟形身影 |
| `MCBIRDFORD:` | `麦克伯德福德：` | 鸟人家族姓氏（McBirdford） |
| `MCBIRDFORD #1`~`#4:` | `麦克伯德福德 #1`~`#4：` | 鸟人评委 |
| `MCBIRDFORDS #2-4:` | `麦克伯德福德 #2-4：` | 鸟人评委 |
| `INTER BOY:` | `中级营男生：` | 夏令营营员 |
| `SENIOR BOY:` | `高级营男生：` | 夏令营营员 |
| `JUNIOR GIRL:` | `初级营女生：` | 夏令营营员 |
| `ALL:` | `众人：` | 众人合声 |

---

## 三、地点、侧边栏立绘与常用术语

1. **地点译名**：
   - `Cabin 20` -> `20号木屋`
   - `Outside Cabin 20` -> `20号木屋外`
   - `Canoe Dock` -> `独木舟码头`
   - `Swimming Dock` -> `游泳码头`
   - `Sailing Dock` -> `帆船码头`
   - `Nature Area` -> `自然区`
   - `Ropes Course` -> `绳索训练场`
   - `Arts and Crafts Hut` -> `美术手工小屋`
   - `Basketball Court` -> `篮球场`
   - `Out on the Lake` -> `湖面上`
2. **时段译名**：
   - `Morning` -> `早晨`
   - `Midday` -> `正午`
   - `Afternoon` -> `下午`
   - `Evening` -> `傍晚`
   - `Night` -> `夜晚`
   - `That night...` -> `那天夜里……`
   - `*(You wake up feeling a bit different than you did yesterday.)*` -> `*(你醒来时，感觉自己和昨天稍微有些不太一样了。)*`
3. **六维心境属性**：
   - `SERENITY` -> `平静`
   - `ALACRITY` -> `机敏`
   - `TENACITY` -> `坚韧`
   - `VIGILANCE` -> `警觉`
   - `MELANCHOLY` -> `忧郁`
   - `GUILE` -> `诡诈`
4. **侧边栏立绘（`*-portrait`）译名**：
   - `***Bridget Leaside (You)***` -> `***布里奇特·利赛德（你）***`
   - `***Mackenzie Singh***` -> `***麦肯齐·辛格***`
   - `***Bell Park***` -> `***贝尔·帕克***`
   - `***Alisha "Sail" Avi***` -> `***艾莉莎·“扬帆”·阿维***`
   - `***Dan "Canoe" Landing***` -> `***丹·“独木舟”·兰丁***`
   - `***TJ "Swim" Phillips***` -> `***TJ·“游泳”·菲利普斯***`
   - `***Taylor Massey***` -> `***泰勒·马西***`
   - `***Taylor Creek***` -> `***泰勒·克里克***`
   - `***Cassidy "Woods" Warden***` -> `***卡西迪·“森林”·沃登***`
   - `***Elizabeth Wei***` -> `***伊丽莎白·魏***`
   - `***Heather "Ropes" Balão***` -> `***海瑟·“绳索”·巴劳***`
   - `***Zoe Price***` -> `***佐伊·普莱斯***`
   - `***Logan "Crafts" Dinowitz***` -> `***洛根·“手工”·迪诺维茨***`
   - `***Deputy***` -> `***副警长***`
   - `***First Mate***` -> `***大副***`
   - `***Coach***` -> `***教练***`
   - `***Manager***` -> `***经纪人***`
   - `***Assistant***` -> `***助手***`
   - `***Fellow Student***` -> `***同学***`

---

## 四、文风要求

- **日常营地对话**：自然、鲜活、地道，还原 14 岁少女布里奇特的吐槽、犹豫、窘迫和冷幽默，以及贝尔的洒脱、敏锐与酷劲。
- **鸟人对话与被鸟化后的辅导员**：使用**刻板、书面、生硬、像劣质机器说明书一样的腔调**（例如“请陈述你的职位名称”、“人类躯体结构存在固有缺陷”、“开始执行人类社交程序”），与人类鲜活的口语形成强烈荒诞反差。
- **双关梗处理**：如 `Bell Wether`（贝尔·韦瑟），可译出字面意思并加自然注释或双关表达（如：“‘韦瑟（Wether，领头阉羊）’？当真？”、“贝尔·韦瑟（Bellwether，领头羊）？？”）。
