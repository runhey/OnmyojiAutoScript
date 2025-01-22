配置注意事项:
1. 由于账号匹配时,阴阳师客户端对手机号信息做了处理,所以配置手机账号时,需要注意与阴阳师客户端显示一致
    例如
    - 手机账号为15355554444,
    - 阴阳师客户端显示为153****4444
    - 所以账号配置为153****4444
2. 配置邮箱账号时,直接填写账号即可,不需要额外处理
3. 账号别名(accountAlias) OCR识别正确率低的产物,多个别名使用#分隔
   建议根据日志显示配置
   例子: 
   - 账号:abc0123@163.com
   - 识别结果 a6co123@163.com
      或者 abc023@163.com 等等千奇百怪的结果
   - 别名配置为 a6co123#abc023#.....
4. appleOrAndroid: true为安卓,false为苹果
5. last_complete_time: 上次完成时间,第一次配置时可以填写为(1970-01-01 00:00:00),后期无需手动修改
6. 仅支持正式服,渠道服暂不支持
   
示例:
```angular2html
[{
   "character": "角色名",
   "svr": "万事屋",
   "account": "150****4444",
   "accountAlias": "150★***4444#150*★**4444#150**★*4444#150***★4444",
   "appleOrAndroid": true,
   "last_complete_time": "2023-01-06 19:15:12.029080"
 },
 {
   "character": "角色名2",
   "svr": "森遥乡",
   "account": "emailAddress@163.com",
   "accountAlias": "emailAddress0#emailAddressO#emailAddresso",
   "appleOrAndroid": true,
   "last_complete_time": "2023-04-06 19:33:01.159141"
}]
```

