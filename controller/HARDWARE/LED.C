#include "led.h"

int Led_Count=500; //LED flicker time control //LED闪烁时间控制

/**************************************************************************
Function: LED interface initialization
Input   : none
Output  : none
函数功能：LED接口初始化
入口参数：无 
返回  值：无
**************************************************************************/
void LED_Init(void)
{
	GPIO_InitTypeDef  GPIO_InitStructure;
	
  RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOD, ENABLE);//使能GPIOB时钟
  GPIO_InitStructure.GPIO_Pin =  LED_R_PIN|LED_G_PIN|LED_B_PIN;//LED对应IO口
  GPIO_InitStructure.GPIO_Mode = GPIO_Mode_OUT;//普通输出模式
  GPIO_InitStructure.GPIO_OType = GPIO_OType_PP;//推挽输出
  GPIO_InitStructure.GPIO_Speed = GPIO_Speed_100MHz;//100MHz
  GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_UP;//上拉
  GPIO_Init(GPIOD, &GPIO_InitStructure);//初始化GPIO
	GPIO_SetBits(GPIOD,LED_R_PIN);
	GPIO_SetBits(GPIOD,LED_G_PIN);
	GPIO_SetBits(GPIOD,LED_B_PIN);
}
/**************************************************************************
Function: Buzzer interface initialized
Input   : none
Output  : none
函数功能：蜂鸣器接口初始化
入口参数：无 
返回  值：无
**************************************************************************/
void Buzzer_Init(void)
{	
	GPIO_InitTypeDef  GPIO_InitStructure;
	
  RCC_AHB1PeriphClockCmd(RCC_AHB1Periph_GPIOD, ENABLE);//使能GPIOB时钟
  GPIO_InitStructure.GPIO_Pin =  Buzzer_PIN;//LED对应IO口
  GPIO_InitStructure.GPIO_Mode = GPIO_Mode_OUT;//普通输出模式
  GPIO_InitStructure.GPIO_OType = GPIO_OType_PP;//推挽输出
  GPIO_InitStructure.GPIO_Speed = GPIO_Speed_100MHz;//100MHz
  GPIO_InitStructure.GPIO_PuPd = GPIO_PuPd_UP;//上拉
  GPIO_Init(GPIOD, &GPIO_InitStructure);//初始化GPIO
}

void TIM6_Init(void)
{
		uint32_t tim_clk = 84000000;  // TIM6 和 TIM7 的时钟频率为 84 MHz
	uint16_t prescaler = (tim_clk / 1000000) - 1;  // 计算预分频，确保定时器频率为 1 MHz

    TIM_TimeBaseInitTypeDef TIM_BaseStructure;
    NVIC_InitTypeDef NVIC_InitStructure;

    // 使能 TIM6 时钟
    RCC_APB1PeriphClockCmd(RCC_APB1Periph_TIM6, ENABLE);

    // 配置 TIM6 为基础定时器，设置定时器频率为 1 MHz（1 微秒计数周期）

	TIM_BaseStructure.TIM_Prescaler = prescaler;  // 设置预分频值


    TIM_BaseStructure.TIM_CounterMode = TIM_CounterMode_Up;  // 向上计数模式
    TIM_BaseStructure.TIM_Period = 1000 - 1;  // 设置定时器周期（例如 1ms）
    TIM_BaseStructure.TIM_ClockDivision = TIM_CKD_DIV1;  // 不分频
    TIM_BaseStructure.TIM_RepetitionCounter = 0;
    TIM_TimeBaseInit(TIM6, &TIM_BaseStructure);  // 初始化定时器 TIM6

    // 配置中断
    TIM_ITConfig(TIM6, TIM_IT_Update, ENABLE);  // 启用定时器更新中断

    // 配置中断优先级
    NVIC_InitStructure.NVIC_IRQChannel = TIM6_DAC_IRQn;
    NVIC_InitStructure.NVIC_IRQChannelPreemptionPriority = 2;
    NVIC_InitStructure.NVIC_IRQChannelSubPriority = 2;
    NVIC_InitStructure.NVIC_IRQChannelCmd = ENABLE;
    NVIC_Init(&NVIC_InitStructure);  // 配置 NVIC

    TIM_Cmd(TIM6, ENABLE);  // 启动 TIM6
}

volatile uint8_t buzzer_level = 0;  // 用于翻转电平

void TIM6_DAC_IRQHandler(void)
{
    if(TIM_GetITStatus(TIM6, TIM_IT_Update) != RESET)
    {
        TIM_ClearITPendingBit(TIM6, TIM_IT_Update);  // 清除中断标志

        if (buzzer_level == 0) {
            GPIO_SetBits(GPIOD, GPIO_Pin_11);  // 设置 PD11 为高电平
            buzzer_level = 1;  // 更新电平状态
        } else {
            GPIO_ResetBits(GPIOD, GPIO_Pin_11);  // 设置 PD11 为低电平
            buzzer_level = 0;  // 更新电平状态
        }
    }
}
void Buzzer_Set_Frequency(uint32_t freq_hz)
{
    if (freq_hz == 0) {
        TIM_Cmd(TIM6, DISABLE);  // 停止定时器
        GPIO_ResetBits(GPIOD, GPIO_Pin_11);  // 关闭蜂鸣器
    } else {
        uint32_t period = 1000000 / (2 * freq_hz) - 1;  // 计算周期（1us）
        TIM6->ARR = (uint16_t)period;  // 设置周期
        TIM6->CNT = 0;  // 重置计数器
        TIM_Cmd(TIM6, ENABLE);  // 启动定时器
    }
}

/**************************************************************************
Function: LED light flashing task
Input   : none
Output  : none
函数功能：LED灯闪烁任务
入口参数：无 
返回  值：无
**************************************************************************/
void led_task(void *pvParameters)
{
    while(1)
    {
		static u8 led_state=0;
		
		led_state = !led_state;
		
		if( Allow_Recharge )
		{
			if( Charging )LED_Purple(led_state);
			else LED_Yellow(led_state);
		}
		else
			LED_Red(led_state);
			
		vTaskDelay(Led_Count); 
    }
}  

/**************************************************************************
Function: The LED flashing
Input   : none
Output  : blink time
函数功能：LED闪烁
入口参数：闪烁时间
返 回 值：无
**************************************************************************/
void Led_Flash(u16 time)
{
	  static int temp;
	  if(0==time) LED_R=0;
	  else		if(++temp==time)	LED_R=~LED_R,temp=0;
}


