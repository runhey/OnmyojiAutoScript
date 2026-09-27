表 1:ext.path 全家桶的消费方(按功能分组)
ext.path 子模块	提供的功能	使用方(alasio/)	用在哪
PathStr(顶层类)	路径对象计算(uppath/joinpath/换后缀等)	logger/writer、backend/app/{restart,frontend}、backend/worker、assets_dev/*、git/fetch/argument、device/search/{base,windows}、codegen/ruff/*、config_dev/{base,gen_index}、config/entry/mod_base、deploy_dev/simple_pip	项目根定位、资源路径拼接、模块路径转 import 名
atomic	原子读写删移(写临时+rename)、CHUNK_SIZE	几乎全仓库:deploy/pack/*、git/stage/*、git/file/*、git/fetch/*、git/eol/*、db/conn、backend/{app,topic}、assets/*、assets_dev/extract、config/table/scan、codegen/{ruff,python,markdown,asar}、base/image/*、logger/{writer,error}、ext/file/*(jsonfile/msgspecfile/yamlfile/yamlconfig)、ext/download	一切落盘 IO 的唯一入口
calc	纯函数路径运算(normpath/joinpath/uppath/get_suffix/get_stem/subpath_to/to_posix/joinnormpath/to_python_import…)	git/stage/{index,gitadd,gitref}、git/file/{loose,idx,gitobject}、base/image/*、assets_dev/*、backend/worker/bridge、backend/app/app、config_dev/gen/*、config/entry/{loader,const}、codegen/ruff、assets/model/*、device/search/base、git/attr	性能敏感处的路径运算、suffix 提取、相对子路径
validate	路径安全校验(防穿越/保留名/长度)	deploy/pack/decode_base、deploy_dev/pack/{encode_base,encode_manifest}、config/table/scan、assets/model/{name,folder}、assets/manager、codegen/asar/{archive,model}	解包/打包/资产命名前的安全闸
iter	目录/文件迭代、CachePathExists	git/stage/gitref、git/eol/constgen、assets/model/folder、deploy_dev/release/cleanup、base/image/imfile、device/search/windows	遍历工作区/Git 对象
makedir	batch_makedirs	deploy/pack/job_base	递归建目录
表 2:ext.file 全家桶的消费方