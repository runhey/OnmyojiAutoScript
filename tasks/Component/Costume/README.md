## 如何添加自定义庭院

1. 在`./tasks/Component/Costume`文件夹下面新建一个你的这个庭院皮肤文件夹比如`mainxxx`

2. 在你的文件夹下面新增一个`image.json`，启动`gui.py`对应工具添加对应的assets

   **很重要很重要，你不要乱划动庭院，如果你留意到游戏在你的停留位置是默认的**

   **在你生成之前需要点击探索然后在回来、再点击町中然后回来，确保你的当前的位置的默认的**

   你需要生成如下的assets:

   - check_main_xxx:   这张图片用来判断是否在庭院的
   - main_goto_exploration_xxx:  这张图片是用来点击"探索"图标的
   - main_goto_summon_xxx:  这张图片是用来点击 ”召唤“
   - main_goto_town_xxx:   町中知道吧
   - pet_house_xxx:  进入宠物屋

3. 执行`./dev_tools/assets_extract.py`这个将会更新`./tasks/Component/Costume/assets.py` 你不需要手动修改这个文件

4. 好了你现在以及输出你这个庭院皮肤的assets了，下面是为其加入 OAS 中

5. 打开`./tasks/Component/Costume/config.py`看到类似这种的，照着填进去

   ```python
   COSTUME_MAIN_2 = 'costume_main_2'  # 琼夜淬光
   ```

6. 打开`./tasks/Component/Costume/costume_base.py`看到类似这种的，照着填进去。

   解释一下，`COSTUME_MAIN_2` 是你刚刚定义的一个庭院类型，后面的第一个key就是原先的assets, 后面的value就是你刚刚输出的要替换的原先的assets。具体的值在`assets.py`文件有定义。照着填没毛病吧。

   ```python
   MainType.COSTUME_MAIN_2: {'I_CHECK_MAIN': 'I_CHECK_MAIN_1',
                                 'I_MAIN_GOTO_EXPLORATION': 'I_MAIN_GOTO_EXPLORATION_1',
                                 'I_MAIN_GOTO_SUMMON': 'I_MAIN_GOTO_SUMMON_1',
                                 'I_MAIN_GOTO_TOWN': 'I_MAIN_GOTO_TOWN_1',
                                 'I_PET_HOUSE': 'I_PET_HOUSE_1', },
   ```

7. 完事之后，你需要测试一下。执行`./tasks/Component/Costume/costume_test.py` 这个文件。

   **在测试之前你需要打开一次 OASX 修改你对应的庭院皮肤的选项**

8. 完事啦？？？哪有那么简单，你没有发现打开 OASX 的时候发现你的选项还是 `costume_main_xxx` 这种吗。你还需要添加一个翻译，[点击这儿](https://runhey.github.io/OnmyojiAutoScript-website/docs/development/user-option#7翻译)