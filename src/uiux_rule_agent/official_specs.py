from __future__ import annotations

import csv
from io import StringIO
from urllib.parse import urlparse

from .models import RuleRow

_ANT_DESIGN_COLORS_URL = "https://ant.design/docs/spec/colors-cn/"
_ANT_DESIGN_FONT_URL = "https://ant.design/docs/spec/font-cn/"

_ANT_DESIGN_COLORS_RULES = '''rule_id,prefix,layer,page_type,subject,component,state,property_name,condition_if,then_clause,else_clause,default_value,preferred_pattern,anti_pattern,evidence,source_ref
FDN-001,FDN,foundation,foundation,设计层颜色模型,,default,color-model,If 定义设计层颜色模型,Then color-model 必须为 HSB,Else 禁止在同一规范中混用多个主色彩模型,HSB,在设计稿和团队评审语言中统一使用 HSB,不要把 RGB 或 HSL 作为团队主沟通模型,官方页面说明设计团队倾向采用 HSB 进行设计,https://ant.design/docs/spec/colors-cn/
FDN-002,FDN,foundation,foundation,系统级色彩体系-基础色板,,default,required-palette-group,If 定义系统级色彩体系,Then required-palette-group 必须包含 foundation-palette,Else 禁止只定义产品色而缺失基础色板,foundation-palette,先建立基础色板再映射到品牌与业务语义,不要直接从零散品牌色开始定义全站颜色,官方页面将基础色板列为系统级色彩体系的一部分,https://ant.design/docs/spec/colors-cn/
FDN-003,FDN,foundation,foundation,系统级色彩体系-中性色板,,default,required-palette-group,If 定义系统级色彩体系,Then required-palette-group 必须包含 neutral-palette,Else 禁止跳过中性色层直接拼接文本和边框色,neutral-palette,将文本 边框 背景与分割线统一收敛到中性色板,不要让中性色散落为临时灰度值,官方页面将中性色板列为系统级色彩体系的一部分,https://ant.design/docs/spec/colors-cn/
FDN-004,FDN,foundation,foundation,系统级色彩体系-数据可视化色板,,default,required-palette-group,If 定义系统级色彩体系,Then required-palette-group 必须包含 data-visualization-palette,Else 禁止复用界面功能色替代图表色体系,data-visualization-palette,将图表用色与界面功能色分层管理,不要把图表色直接混入普通界面 token,官方页面将数据可视化色板列为系统级色彩体系的一部分,https://ant.design/docs/spec/colors-cn/
FDN-005,FDN,foundation,foundation,基础色板,,default,hue-family-count,If 构建基础色板,Then hue-family-count 必须为 12,Else 禁止减少为无法覆盖常见业务语义的色相数量,12,按统一色相家族维护基础色板,不要只保留少量色相导致扩展性不足,官方页面说明基础色板由 12 个主色构成,https://ant.design/docs/spec/colors-cn/
FDN-006,FDN,foundation,foundation,基础色板,,default,tone-count-per-family,If 为单个基础色相生成衍生色,Then tone-count-per-family 必须为 10,Else 禁止为不同色相定义不等长的衍生层级,10,为每个色相提供一致的 10 阶衍生色,不要让不同色相家族拥有不一致的色阶数,官方页面展示每个基础色相均配有 10 个色阶,https://ant.design/docs/spec/colors-cn/
FDN-007,FDN,foundation,foundation,基础色板,,default,hue-family-set,If 定义基础色板色相家族,Then hue-family-set 必须为 red|volcano|orange|gold|yellow|lime|green|cyan|blue|geekblue|purple|magenta,Else 禁止引入未纳入系统色板的临时主色家族,red|volcano|orange|gold|yellow|lime|green|cyan|blue|geekblue|purple|magenta,优先从官方 12 个色相家族中选取主色并生成衍生色,不要为基础色板随意新增非体系化色相家族,官方页面列出了 12 个基础色相家族,https://ant.design/docs/spec/colors-cn/
FDN-008,FDN,foundation,foundation,中性色板,,default,tone-count,If 构建中性色板,Then tone-count 必须为 13,Else 禁止用零散黑白灰值替代完整中性色层级,13,按从白到黑的连续层级维护中性色,不要把中性色简化成少量孤立灰度,官方页面说明中性色板包含从白到黑的 13 个颜色,https://ant.design/docs/spec/colors-cn/
FDN-009,FDN,foundation,foundation,品牌主色,,default,selection-strategy,If 从基础色板选择品牌主色,Then selection-strategy 必须为 shade-6,Else 禁止从过浅或过深色阶直接充当品牌主色,shade-6,从浅到深选择第 6 个色阶作为品牌主色 token,不要把 1 到 5 或 7 到 10 号色阶直接作为默认品牌主色,官方页面建议选择色板从浅至深的第六个颜色作为主色,https://ant.design/docs/spec/colors-cn/
FDN-010,FDN,foundation,foundation,品牌主色,,default,primary-color,If 采用 Ant Design 默认品牌主色,Then primary-color 必须为 #1677FF,Else 禁止在未重建完整色板前直接替换默认品牌主色,#1677FF,默认品牌主色使用 Ant Design 蓝色主色 token,不要在没有完整衍生色的情况下随意替换默认品牌蓝,官方页面给出 Ant Design 品牌主色为 #1677FF,https://ant.design/docs/spec/colors-cn/
FDN-011,FDN,foundation,foundation,品牌主色使用场景-关键行动点,,default,allowed-use-case,If 需要为关键行动点分配颜色,Then allowed-use-case 必须包含 brand-primary,Else 禁止用次要色承担默认主行动入口,brand-primary,将主按钮和关键 CTA 收敛到品牌主色,不要让关键行动点颜色随页面变化,官方页面将关键行动点列为品牌主色应用场景,https://ant.design/docs/spec/colors-cn/
FDN-012,FDN,foundation,foundation,品牌主色使用场景-操作状态,,default,allowed-use-case,If 需要表达操作状态,Then allowed-use-case 必须允许使用 brand-primary,Else 禁止把品牌主色完全排除在操作状态体系之外,brand-primary,在强调操作反馈时优先复用品牌主色语义,不要为常规操作状态额外发明风格无关的主色,官方页面将操作状态列为品牌主色应用场景,https://ant.design/docs/spec/colors-cn/
FDN-013,FDN,foundation,foundation,品牌主色使用场景-重要信息高亮,,default,allowed-use-case,If 需要高亮重要信息,Then allowed-use-case 必须允许使用 brand-primary,Else 禁止把重要信息高亮拆成多套竞争色,brand-primary,重要信息高亮优先复用品牌主色语义,不要为同类高亮信息混用多种主强调色,官方页面将重要信息高亮列为品牌主色应用场景,https://ant.design/docs/spec/colors-cn/
FDN-014,FDN,foundation,foundation,品牌主色使用场景-图形化,,default,allowed-use-case,If 需要在图形化场景中表达品牌一致性,Then allowed-use-case 必须允许使用 brand-primary,Else 禁止在图形化主视觉中完全丢失品牌主色,brand-primary,在需要品牌识别的图形化场景使用品牌主色,不要让图形化主视觉脱离品牌主色体系,官方页面将图形化列为品牌主色应用场景,https://ant.design/docs/spec/colors-cn/
FDN-015,FDN,foundation,foundation,功能色,,default,semantic-mapping,If 定义功能色,Then semantic-mapping 必须为 align-with-user-cognition,Else 禁止让成功 失败 警示等语义违背用户常识,align-with-user-cognition,让功能色与用户既有语义认知保持一致,不要让状态色和语义产生反直觉映射,官方页面强调功能色需要遵守用户对色彩的基本认知,https://ant.design/docs/spec/colors-cn/
FDN-016,FDN,foundation,foundation,功能色,,default,consistency-scope,If 在同一产品体系中定义功能色,Then consistency-scope 必须为 product-wide-consistency,Else 禁止在不同模块为相同状态定义不同功能色,product-wide-consistency,在整套产品内统一成功 失败 提醒等状态色,不要让同一状态在不同页面使用不同颜色,官方页面建议功能色在一套产品体系下尽量保持一致,https://ant.design/docs/spec/colors-cn/
FDN-017,FDN,foundation,foundation,功能色,,default,customization-limit,If 扩展功能色体系,Then customization-limit 必须为 low-customization,Else 禁止加入过多自定义状态色干扰认知,low-customization,只在必要时少量扩展功能色,不要堆叠过多自定义功能色,官方页面建议避免过多自定义干扰用户认知体验,https://ant.design/docs/spec/colors-cn/
FDN-018,FDN,foundation,foundation,标题文本-浅色背景,,default,color,If 背景主题 = light and 文本角色 = title,Then color 必须为 #000000E0,Else 禁止在浅色背景标题中使用未定义深色文本值,#000000E0,浅色背景标题使用高对比度中性色 token,不要在浅色背景标题中直接替换为其他黑灰值,官方页面给出标题字体浅色背景值为 #000000E0,https://ant.design/docs/spec/colors-cn/
FDN-019,FDN,foundation,foundation,标题文本-深色背景,,default,color,If 背景主题 = dark and 文本角色 = title,Then color 必须为 #FFFFFFD9,Else 禁止在深色背景标题中使用未定义浅色文本值,#FFFFFFD9,深色背景标题使用高对比度浅色中性色 token,不要在深色背景标题中随意提高或降低透明度,#FFFFFFD9 来自官方页面的标题字体深色背景值,https://ant.design/docs/spec/colors-cn/
FDN-020,FDN,foundation,foundation,一级文本-浅色背景,,default,color,If 背景主题 = light and 文本角色 = primary-text,Then color 必须为 #000000E0,Else 禁止在浅色背景一级文本中使用未定义文本色,#000000E0,一级正文与标题共享高可读性浅底深字 token,不要在一级文本中擅自降低透明度,官方页面给出一级文本浅色背景值为 #000000E0,https://ant.design/docs/spec/colors-cn/
FDN-021,FDN,foundation,foundation,一级文本-深色背景,,default,color,If 背景主题 = dark and 文本角色 = primary-text,Then color 必须为 #FFFFFFD9,Else 禁止在深色背景一级文本中使用未定义文本色,#FFFFFFD9,一级正文在深色背景使用高可读性浅字 token,不要在深色背景一级文本中改用纯白以外的临时值,官方页面给出一级文本深色背景值为 #FFFFFFD9,https://ant.design/docs/spec/colors-cn/
FDN-022,FDN,foundation,foundation,二级文本-浅色背景,,default,color,If 背景主题 = light and 文本角色 = secondary-text,Then color 必须为 #000000A6,Else 禁止在浅色背景二级文本中使用未定义灰度,#000000A6,二级文本使用降低一级强调度的中性色 token,不要让二级文本与一级文本失去层级差异,官方页面给出二级文本浅色背景值为 #000000A6,https://ant.design/docs/spec/colors-cn/
FDN-023,FDN,foundation,foundation,二级文本-深色背景,,default,color,If 背景主题 = dark and 文本角色 = secondary-text,Then color 必须为 #FFFFFFA6,Else 禁止在深色背景二级文本中使用未定义灰度,#FFFFFFA6,深色背景二级文本使用降低强调度的浅色 token,不要让深色背景二级文本与一级文本无差异,#FFFFFFA6 来自官方页面的二级文本深色背景值,https://ant.design/docs/spec/colors-cn/
FDN-024,FDN,foundation,foundation,禁用文本-浅色背景,,default,color,If 背景主题 = light and 文本角色 = disabled-text,Then color 必须为 #00000040,Else 禁止在浅色背景禁用文本中使用过强对比色,#00000040,禁用文本使用低强调度中性色 token,不要让禁用文本看起来仍像可操作内容,官方页面给出禁用字体浅色背景值为 #00000040,https://ant.design/docs/spec/colors-cn/
FDN-025,FDN,foundation,foundation,禁用文本-深色背景,,default,color,If 背景主题 = dark and 文本角色 = disabled-text,Then color 必须为 #FFFFFF40,Else 禁止在深色背景禁用文本中使用过强对比色,#FFFFFF40,深色背景禁用文本使用低强调度浅色 token,不要让禁用文本在深色主题下仍然过度显眼,#FFFFFF40 来自官方页面的禁用字体深色背景值,https://ant.design/docs/spec/colors-cn/
FDN-026,FDN,foundation,foundation,一级边框-浅色背景,,default,color,If 背景主题 = light and 元素角色 = primary-border,Then color 必须为 #D9D9D9,Else 禁止在浅色主题一级边框中使用未定义边框灰度,#D9D9D9,浅色主题一级边框使用稳定的浅灰边框 token,不要用任意灰度替换一级边框色,官方页面给出一级边框浅色背景值为 #D9D9D9,https://ant.design/docs/spec/colors-cn/
FDN-027,FDN,foundation,foundation,一级边框-深色背景,,default,color,If 背景主题 = dark and 元素角色 = primary-border,Then color 必须为 #424242,Else 禁止在深色主题一级边框中使用未定义边框灰度,#424242,深色主题一级边框使用低亮度边框 token,不要用过亮边框破坏深色主题层次,官方页面给出一级边框深色背景值为 #424242,https://ant.design/docs/spec/colors-cn/
FDN-028,FDN,foundation,foundation,分割线-浅色背景,,default,color,If 背景主题 = light and 元素角色 = divider,Then color 必须为 #0505050F,Else 禁止在浅色主题分割线中使用过重实线颜色,#0505050F,分割线优先使用低不透明度中性色 token,不要让分割线比正文更抢眼,官方页面给出分割线浅色背景值为 #0505050F,https://ant.design/docs/spec/colors-cn/
FDN-029,FDN,foundation,foundation,分割线-深色背景,,default,color,If 背景主题 = dark and 元素角色 = divider,Then color 必须为 #FDFDFD1F,Else 禁止在深色主题分割线中使用过亮或过重颜色,#FDFDFD1F,深色主题分割线使用低不透明度浅色 token,不要让分割线在深色界面中形成刺眼高对比,#FDFDFD1F 来自官方页面的分割线深色背景值,https://ant.design/docs/spec/colors-cn/
FDN-030,FDN,foundation,foundation,布局背景-浅色背景,,default,color,If 背景主题 = light and 元素角色 = layout-background,Then color 必须为 #F5F5F5,Else 禁止在浅色主题布局背景中使用未定义页面灰底,#F5F5F5,浅色主题布局背景使用稳定低饱和中性色,不要在浅色页面背景中使用过强彩色或纯白替代值,官方页面给出布局背景浅色主题值为 #F5F5F5,https://ant.design/docs/spec/colors-cn/
FDN-031,FDN,foundation,foundation,布局背景-深色背景,,default,color,If 背景主题 = dark and 元素角色 = layout-background,Then color 必须为 #000000,Else 禁止在深色主题布局背景中使用未定义底色,#000000,深色主题布局背景使用统一深底 token,不要在深色布局背景中混入多个接近黑色的临时值,官方页面给出布局背景深色主题值为 #000000,https://ant.design/docs/spec/colors-cn/
FDN-032,FDN,foundation,foundation,中性色实现方式,,default,implementation-pattern,If 落地中性色 token,Then implementation-pattern 必须为 opacity-based-black-white,Else 禁止直接用大量彼此独立的灰值替代透明度体系,opacity-based-black-white,以黑白基色叠加透明度定义中性色 token,不要把中性色实现成难以维护的离散灰值集合,官方页面说明中性色在落地时按透明度方式实现,https://ant.design/docs/spec/colors-cn/
FDN-033,FDN,foundation,foundation,企业级色彩应用态度,,default,usage-attitude,If 设计企业级产品配色,Then usage-attitude 必须为 restrained,Else 禁止把高饱和装饰性色彩作为默认界面策略,restrained,优先让颜色服务于效率与信息传达,不要让颜色成为主要干扰源,官方页面说明企业级产品中的色彩使用应保持克制,https://ant.design/docs/spec/colors-cn/
FDN-034,FDN,foundation,foundation,企业级色彩用途-信息传递,,default,allowed-purpose,If 为企业级界面分配颜色用途,Then allowed-purpose 必须包含 information-transfer,Else 禁止使用纯装饰性颜色替代信息表达,information-transfer,让颜色先承担信息层级与语义表达,不要为装饰目的优先占用主色资源,官方页面说明企业级产品中的色彩更多基于信息传递目的,https://ant.design/docs/spec/colors-cn/
FDN-035,FDN,foundation,foundation,企业级色彩用途-操作引导,,default,allowed-purpose,If 为企业级界面分配颜色用途,Then allowed-purpose 必须包含 operation-guidance,Else 禁止让关键操作入口缺失明确颜色引导,operation-guidance,用颜色辅助用户识别关键操作路径,不要让操作引导色与普通文本色无差异,官方页面说明企业级产品中的色彩更多基于操作引导目的,https://ant.design/docs/spec/colors-cn/
FDN-036,FDN,foundation,foundation,企业级色彩用途-交互反馈,,default,allowed-purpose,If 为企业级界面分配颜色用途,Then allowed-purpose 必须包含 interaction-feedback,Else 禁止让状态反馈缺失清晰色彩语义,interaction-feedback,用颜色表达成功 失败 提醒等反馈状态,不要让反馈颜色与背景或正文混淆,官方页面说明企业级产品中的色彩更多基于交互反馈目的,https://ant.design/docs/spec/colors-cn/
FDN-037,FDN,foundation,foundation,企业级色彩例外场景,,default,exception-scope,If 页面类型 = illustration-or-showcase,Then exception-scope 可以放宽克制型配色,Else 禁止在常规企业级界面中随意突破克制原则,illustration-or-showcase,仅在配图 插画 或展示性页面适度放宽色彩约束,不要把展示型配色直接复用到常规业务界面,官方页面说明配图插画与展示性页面可适度打破克制思路,https://ant.design/docs/spec/colors-cn/
'''

_ANT_DESIGN_FONT_RULES = '''rule_id,prefix,layer,page_type,subject,component,state,property_name,condition_if,then_clause,else_clause,default_value,preferred_pattern,anti_pattern,evidence,source_ref
FDN-038,FDN,foundation,foundation,字体家族选择策略,,default,selection-strategy,If 定义系统默认字体家族,Then selection-strategy 必须为 system-ui-first,Else 禁止优先使用非系统字体作为全局默认字体,system-ui-first,优先使用系统默认界面字体并补充屏显友好的备用字体库,不要把品牌展示字体直接作为企业级界面默认字体,官方页面说明字体家族优先使用系统默认界面字体,https://ant.design/docs/spec/font-cn/
FDN-039,FDN,foundation,foundation,默认字体家族,,default,font-family,"If 定义全局默认 font-family","Then font-family 必须为 ""-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji'""",Else 禁止定义缺乏跨平台备用字体的局部字体栈,"-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji'",将官方系统字体栈作为全局基础 token 统一复用,不要在不同模块维护多套互不兼容的默认字体栈,官方页面给出推荐的系统字体栈,https://ant.design/docs/spec/font-cn/
FDN-040,FDN,foundation,foundation,数字对齐字体特性,,default,font-variant-numeric,If 数字需要进行纵向对比展示,Then font-variant-numeric 必须为 tabular-nums,Else 禁止在纵向比对场景使用非等宽数字,tabular-nums,在表格 统计卡片 财务数字等纵向对比场景启用等宽数字,不要让同列数字因宽度不一致导致难以比较,官方页面建议数字纵向对比场景使用 tabular-nums,https://ant.design/docs/spec/font-cn/
FDN-041,FDN,foundation,foundation,主字体字号,,default,font-size,If 定义系统主字体,Then font-size 必须为 14px,Else 禁止继续沿用 12px 作为企业级中后台默认正文大小,14px,将 14px 作为默认正文与交互文本的基础字号,不要把 12px 设为中后台默认主字号,官方页面说明主字体由 12 升级至 14,https://ant.design/docs/spec/font-cn/
FDN-042,FDN,foundation,foundation,主字体行高,,default,line-height,If 定义系统主字体,Then line-height 必须为 22px,Else 禁止让默认正文行高脱离主字号基线,22px,默认正文与基础交互文本使用 22px 行高,不要为默认正文设置破坏阅读节奏的任意行高,官方页面说明主字体 14 对应的行高为 22,https://ant.design/docs/spec/font-cn/
FDN-043,FDN,foundation,foundation,字阶体系容量,,default,font-scale-count,If 构建字阶体系,Then font-scale-count 必须为 10,Else 禁止定义过少或无规律的字号层级,10,围绕统一字阶表维护字号与行高层级,不要用零散字号拼接出伪字阶体系,官方页面说明 Ant Design 定义了 10 个不同尺寸的字体及对应行高,https://ant.design/docs/spec/font-cn/
FDN-044,FDN,foundation,foundation,非展示型页面字阶使用数量,,default,font-scale-usage-count,If 页面类型 != display,Then font-scale-usage-count 必须控制在 3-5 种,Else 可以按展示需要适度放宽,3-5,在业务系统中用有限字阶建立稳定层级,不要在常规页面中堆叠大量字号制造视觉重点,官方页面建议展示型页面除外时字阶尽量控制在 3-5 种之间,https://ant.design/docs/spec/font-cn/
FDN-045,FDN,foundation,foundation,默认字重集合,,default,font-weight-set,If 定义常规字体字重,Then font-weight-set 必须包含 400|500,Else 禁止在常规文本体系中滥用过多字重层级,400|500,常规文本优先只使用 regular 与 medium 两档字重,不要在日常界面中无意义混入大量字重,官方页面说明多数情况下只出现 regular 和 medium,https://ant.design/docs/spec/font-cn/
FDN-046,FDN,foundation,foundation,Regular 字重,,default,font-weight,If 文本强调级别 = regular,Then font-weight 必须为 400,Else 禁止把 regular 映射为其他权重,400,将 400 作为默认正文与弱强调文本基线权重,不要让 regular 与 medium 的语义混淆,官方页面说明 regular 对应代码中的 400,https://ant.design/docs/spec/font-cn/
FDN-047,FDN,foundation,foundation,Medium 字重,,default,font-weight,If 文本强调级别 = medium,Then font-weight 必须为 500,Else 禁止把 medium 映射为其他权重,500,将 500 作为常规强调文本的标准权重,不要让 medium 失去统一的强调强度,官方页面说明 medium 对应代码中的 500,https://ant.design/docs/spec/font-cn/
FDN-048,FDN,foundation,foundation,英文加粗字重,,default,font-weight,If 文本语言 = english and 需要加粗强调,Then font-weight 必须为 600,Else 禁止在非英文普通场景中默认使用 semibold,600,仅在英文加粗强调时使用 semibold,不要把 600 扩散为全局默认强调字重,官方页面说明英文字体加粗情况下采用 semibold 600,https://ant.design/docs/spec/font-cn/
FDN-049,FDN,foundation,foundation,文本与背景对比度,,default,contrast-ratio,If 定义正文或标题文本颜色,Then contrast-ratio 必须 >= 7:1,Else 禁止让文本与背景颜色过近导致可读性下降,>=7:1 AAA,按 WCAG AAA 对比度标准校验正文 标题与背景 token,不要使用低于 AAA 可读性的文本背景配色组合,官方页面说明正文文本 标题与背景色之间保持在 7:1 以上的 AAA 级对比度,https://ant.design/docs/spec/font-cn/
FDN-050,FDN,foundation,foundation,字体系统规划维度,,default,planning-categories,If 建立同一系统的字体体系,Then planning-categories 必须包含 primary|secondary|auxiliary|title|display,Else 禁止在缺少全局分类的情况下直接逐页定义字体样式,primary|secondary|auxiliary|title|display,先统一规划主 次 辅助 标题 展示等字体类别再落地场景,不要跳过体系规划直接在页面中零散定义文本样式,官方页面建议先对主 次 辅助 标题 展示等类别统一规划,https://ant.design/docs/spec/font-cn/
FDN-051,FDN,foundation,foundation,字体样式使用原则,,default,usage-attitude,If 定义字体系统视觉策略,Then usage-attitude 必须为 less-is-more,Else 禁止通过大量字阶 颜色 字重堆叠视觉强调,less-is-more,用尽量少的字体样式实现层级与对比,不要毫无意义地使用大量字阶 颜色 字重强调重点,官方页面在建议部分强调少即是多,https://ant.design/docs/spec/font-cn/
FDN-052,FDN,foundation,foundation,拉开字阶差距的选择方式,,default,scale-selection-pattern,If 需要显著拉开字号层级差距,Then scale-selection-pattern 优先为 leap-selection,Else 禁止只通过相邻微调字号制造弱层级,leap-selection,在需要更强层级时从字阶表中跳跃选择字号,不要只做细碎的相邻字号微调导致层级不清,官方页面建议在需要拉开差距时尝试跳跃地选择字体大小,https://ant.design/docs/spec/font-cn/
'''


def _normalize_url(value: str) -> str:
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return value
    path = parsed.path.rstrip("/") + "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _rows_from_csv(csv_text: str) -> list[RuleRow]:
    rows: list[RuleRow] = []
    reader = csv.DictReader(StringIO(csv_text))
    for row in reader:
        rows.append(
            RuleRow(
                prefix=row["prefix"],
                layer=row["layer"],
                page_type=row["page_type"],
                subject=row["subject"],
                component=row["component"],
                state=row["state"],
                property_name=row["property_name"],
                condition_if=row["condition_if"],
                then_clause=row["then_clause"],
                else_clause=row["else_clause"],
                default_value=row["default_value"],
                preferred_pattern=row["preferred_pattern"],
                anti_pattern=row["anti_pattern"],
                evidence=row["evidence"],
                source_ref=row["source_ref"],
                rule_id="",
            )
        )
    return rows


def match_official_spec_rules(input_value: str) -> list[RuleRow] | None:
    normalized = _normalize_url(input_value)
    if normalized == _ANT_DESIGN_COLORS_URL:
        return _rows_from_csv(_ANT_DESIGN_COLORS_RULES)
    if normalized == _ANT_DESIGN_FONT_URL:
        return _rows_from_csv(_ANT_DESIGN_FONT_RULES)
    return None
