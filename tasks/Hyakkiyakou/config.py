from pydantic import BaseModel, Field, field_validator
from enum import Enum

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, Time


class ModelPrecision(str, Enum):
    FP32 = 'FP32'
    INT8 = 'INT8'

class InferenceEngine(str, Enum):
    ONNXRUNTIME = 'Onnxruntime'
    TENSORRT = 'TensorRT'

class ScreenshotMethod(str, Enum):
    WINDOW_BACKGROUND = 'window_background'
    NEMU_IPC = 'nemu_ipc'


class HyakkiyakouConfig(ConfigBase):
    hya_limit_time: Time = Field(default=Time(minute=20), description='hya_limit_time_help')
    hya_limit_count: int = Field(default=10, description='hya_limit_count_help')
    hya_invite_friend: bool = Field(default=False, description='hya_invite_friend_help')
    # 自动调整豆子数量
    hya_auto_bean: bool = Field(default=False, description='hya_auto_bean_help')
    hya_priorities: str = Field(default='', description='hya_priorities_help')
    hya_sp: float = Field(default=1., description='hya_sp_help')
    hya_ssr: float = Field(default=1., description='hya_ssr_help')
    hya_sr: float = Field(default=0.7, description='hya_sr_help')
    hya_r: float = Field(default=0.3, description='hya_r_help')
    hya_n: float = Field(default=0.0, description='hya_n_help')
    # 呱太和N卡不是一个东西
    hya_g: float = Field(default=0.0, description='hya_g_help')


class HyakkiyakouModels(ConfigBase):
    # 置信度阈值
    conf_threshold: float = Field(default=0.6, description='conf_threshold_help')
    # nms阈值
    iou_threshold: float = Field(default=0.7, description='iou_threshold_help')
    # 模型的推理精度 目前全部是fp32
    model_precision: ModelPrecision = Field(default=ModelPrecision.FP32, description='model_precision_help')
    # 推理引擎 目前全部是onnxruntime
    inference_engine: InferenceEngine = Field(default=InferenceEngine.ONNXRUNTIME, description='inference_engine_help')


class DebugConfig(ConfigBase):
    # 运行期间现实每一张的跟踪结果
    hya_show: bool = Field(default=False, description='hya_show_help')
    # 输出更多调试信息， 给使用者显示的
    hya_info: bool = Field(default=False, description='hya_info_help')
    # 保存图片，拿去回喂给模型
    continuous_learning: bool = Field(default=False, description='continuous_learning_help')
    # 保存每一张票的结果
    hya_save_result: bool = Field(default=False, description='hya_save_result_help')
    # 单独的设定截屏间隔, 单位ms
    hya_interval: float = Field(default=300, description='hya_interval_help')
    # 单独的截屏设置
    hya_screenshot_method: ScreenshotMethod = Field(default=ScreenshotMethod.WINDOW_BACKGROUND,
                                                    description='hya_screenshot')

    @field_validator('continuous_learning', mode='after')
    @classmethod
    def false_continuous_learning(cls, v):
        if v:
            return False
        return False


class Hyakkiyakou(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    hyakkiyakou_config: HyakkiyakouConfig = Field(default_factory=HyakkiyakouConfig)
    hyakkiyakou_models: HyakkiyakouModels = Field(default_factory=HyakkiyakouModels)
    debug_config: DebugConfig = Field(default_factory=DebugConfig)


