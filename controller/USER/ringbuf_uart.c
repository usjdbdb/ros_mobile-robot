/**
 * @file    ringbuf_uart.c
 * @brief   串口环形缓冲区实现（单生产者/单消费者，无锁设计）
 *
 * === 设计要点 ===
 * 1. 缓冲区大小必须是 2 的幂（如 64/128/256），使用位掩码代替取模运算
 * 2. 采用"牺牲一个字节"策略区分空/满状态：
 *      空:  head == tail
 *      满:  (head + 1) & mask == tail
 *    有效容量 = 缓冲区总大小 - 1
 * 3. 单生产者/单消费者无锁设计：
 *      - head 只被生产者（如串口ISR）修改，消费者只读不写
 *      - tail 只被消费者（如主循环）修改，生产者只读不写
 *      - 无需关中断，适合 ISR 写入 + 主循环读取的经典串口场景
 * 4. 32 位 head/tail 在 32 位处理器上对齐读写是原子的；8/16 位 MCU 需额外临界区保护
 *
 * === 使用方法 ===
 *   1. 全局定义一个 ringbuf_t 和一个 uint8_t 数组
 *   2. ringbuf_init() 初始化
 *   3. 串口接收中断里调用 ringbuf_put() / ringbuf_puts()
 *   4. 主循环里调用 ringbuf_get() / ringbuf_gets()
 *
 * === 可提取到头文件的部分（见下方 /* ---- .h begin ---- * / 注释区间） ===
 */


#include <stdint.h>
#include <stdbool.h>


/* ================================================================
 *  可提取到 ringbuf_uart.h 的部分
 * ================================================================ */

typedef struct {
    uint8_t        *buffer;   /* 环形缓冲区存储区指针（用户提供） */
    uint32_t        size;     /* 缓冲区总大小，必须是 2 的幂（如 64/128/256） */
    uint32_t        mask;     /* 位掩码 = size - 1，用于快速取模 */
    volatile uint32_t head;   /* 写指针：下一次写入的位置（仅生产者修改） */
    volatile uint32_t tail;   /* 读指针：下一次读取的位置（仅消费者修改） */
} ringbuf_t;


/* ---------- 初始化和重置 ---------- */
void     ringbuf_init (ringbuf_t *rb, uint8_t *buffer, uint32_t size);
void     ringbuf_reset(ringbuf_t *rb);

/* ---------- 状态查询 ---------- */
bool     ringbuf_is_empty (const ringbuf_t *rb);
bool     ringbuf_is_full  (const ringbuf_t *rb);
uint32_t ringbuf_available(const ringbuf_t *rb);   /* 可读字节数 */
uint32_t ringbuf_free     (const ringbuf_t *rb);   /* 可写字节数 */

/* ---------- 单字节读写 ---------- */
bool     ringbuf_put(ringbuf_t *rb, uint8_t byte);   /* 满则返回 false */
bool     ringbuf_get(ringbuf_t *rb, uint8_t *byte);  /* 空则返回 false */

/* ---------- 批量读写，返回实际读写的字节数 ---------- */
uint32_t ringbuf_puts(ringbuf_t *rb, const uint8_t *data, uint32_t len);
uint32_t ringbuf_gets(ringbuf_t *rb, uint8_t *data, uint32_t len);

/* ---------- 查看但不取出 ---------- */
int      ringbuf_peek(const ringbuf_t *rb, uint32_t offset, uint8_t *byte);
          /* offset=0 返回队首字节；返回 0 成功，-1 失败 */

/* ================================================================
 *  实现部分
 * ================================================================ */

/* -------------------------------------------------------------------
 *  初始化
 *   - size 必须是 2 的幂，否则返回不作任何操作
 *   - 有效容量 = size - 1（牺牲一个字节区分空/满）
 * ------------------------------------------------------------------- */
void ringbuf_init(ringbuf_t *rb, uint8_t *buffer, uint32_t size)
{
    /* 校验 size 是否为 2 的幂 */
    if (size == 0 || (size & (size - 1)) != 0) {
        return;   /* 无效参数，静默返回 */
    }

    rb->buffer = buffer;
    rb->size   = size;
    rb->mask   = size - 1;
    rb->head   = 0;
    rb->tail   = 0;
}

/* -------------------------------------------------------------------
 *  重置缓冲区（清空所有数据）
 *  仅由消费者调用（或确保没有并发访问时调用）
 * ------------------------------------------------------------------- */
void ringbuf_reset(ringbuf_t *rb)
{
    rb->head = 0;
    rb->tail = 0;
}

/* -------------------------------------------------------------------
 *  判断是否为空
 * ------------------------------------------------------------------- */
bool ringbuf_is_empty(const ringbuf_t *rb)
{
    return rb->head == rb->tail;
}

/* -------------------------------------------------------------------
 *  判断是否已满
 * ------------------------------------------------------------------- */
bool ringbuf_is_full(const ringbuf_t *rb)
{
    return ((rb->head + 1) & rb->mask) == rb->tail;
}

/* -------------------------------------------------------------------
 *  可读字节数
 *  head 可能被 ISR 并发修改，但只会增大 → 返回值是"至少可读"的下界
 *  (head - tail) & mask：无论谁大谁小，均得出正确的可用字节数
 * ------------------------------------------------------------------- */
uint32_t ringbuf_available(const ringbuf_t *rb)
{
    return (rb->head - rb->tail) & rb->mask;
}

/* -------------------------------------------------------------------
 *  可写字节数（空闲空间）
 * ------------------------------------------------------------------- */
uint32_t ringbuf_free(const ringbuf_t *rb)
{
    return (rb->tail - rb->head - 1) & rb->mask;
}

/* -------------------------------------------------------------------
 *  写入一个字节
 *   生产者调用（通常在串口接收 ISR 中）
 *   返回 true  = 写入成功
 *   返回 false = 缓冲区满，数据被丢弃
 * ------------------------------------------------------------------- */
bool ringbuf_put(ringbuf_t *rb, uint8_t byte)
{
    uint32_t head = rb->head;

    /* 判断是否满：(head + 1) & mask == tail */
    if (((head + 1) & rb->mask) == rb->tail) {
        return false;   /* 缓冲区满，丢弃 */
    }

    rb->buffer[head] = byte;
    rb->head = (head + 1) & rb->mask;
    return true;
}

/* -------------------------------------------------------------------
 *  读取一个字节
 *   消费者调用（通常在主循环或任务中）
 *   返回 true  = 读取成功，数据写入 *byte
 *   返回 false = 缓冲区空
 * ------------------------------------------------------------------- */
bool ringbuf_get(ringbuf_t *rb, uint8_t *byte)
{
    uint32_t tail = rb->tail;

    if (tail == rb->head) {
        return false;   /* 缓冲区空 */
    }

    *byte = rb->buffer[tail];
    rb->tail = (tail + 1) & rb->mask;
    return true;
}

/* -------------------------------------------------------------------
 *  批量写入
 *   尽量写入 len 个字节，返回实际写入数
 *   环形缓冲区可能跨尾部 → 分两段拷贝
 * ------------------------------------------------------------------- */
uint32_t ringbuf_puts(ringbuf_t *rb, const uint8_t *data, uint32_t len)
{
    uint32_t free   = ringbuf_free(rb);
    uint32_t head   = rb->head;
    uint32_t mask   = rb->mask;
    uint32_t write_cnt;

    /* 截断到可用空间 */
    if (len > free) {
        len = free;
    }
    if (len == 0) {
        return 0;
    }

    write_cnt = len;

    /* 第一段：从 head 到缓冲区末尾 */
    uint32_t first = mask + 1 - head;   /* 从 head 到尾部的连续空间 */
    if (first > len) {
        first = len;
    }

    /* 逐字节拷贝第一段（避免 memcpy 引入额外依赖，用户可自行替换） */
    for (uint32_t i = 0; i < first; i++) {
        rb->buffer[head + i] = data[i];
    }

    /* 第二段：从缓冲区头部开始 */
    if (len > first) {
        uint32_t second = len - first;
        for (uint32_t i = 0; i < second; i++) {
            rb->buffer[i] = data[first + i];
        }
    }

    rb->head = (head + len) & mask;
    return write_cnt;
}

/* -------------------------------------------------------------------
 *  批量读取
 *   尽量读取 len 个字节到 data，返回实际读取数
 * ------------------------------------------------------------------- */
uint32_t ringbuf_gets(ringbuf_t *rb, uint8_t *data, uint32_t len)
{
    uint32_t avail  = ringbuf_available(rb);
    uint32_t tail   = rb->tail;
    uint32_t mask   = rb->mask;
    uint32_t read_cnt;

    if (len > avail) {
        len = avail;
    }
    if (len == 0) {
        return 0;
    }

    read_cnt = len;

    /* 第一段：从 tail 到缓冲区末尾 */
    uint32_t first = mask + 1 - tail;
    if (first > len) {
        first = len;
    }

    for (uint32_t i = 0; i < first; i++) {
        data[i] = rb->buffer[tail + i];
    }

    /* 第二段：从缓冲区头部开始 */
    if (len > first) {
        uint32_t second = len - first;
        for (uint32_t i = 0; i < second; i++) {
            data[first + i] = rb->buffer[i];
        }
    }

    rb->tail = (tail + len) & mask;
    return read_cnt;
}

/* -------------------------------------------------------------------
 *  查看缓冲区中指定偏移处的字节，不取出
 *   offset = 0 表示队首（下一个要读出的字节）
 *   返回 0 成功，-1 失败（空或偏移越界）
 * ------------------------------------------------------------------- */
int ringbuf_peek(const ringbuf_t *rb, uint32_t offset, uint8_t *byte)
{
    uint32_t avail = ringbuf_available(rb);

    if (offset >= avail) {
        return -1;
    }

    *byte = rb->buffer[(rb->tail + offset) & rb->mask];
    return 0;
}


/* ================================================================
 *  使用示例（可删除）
 * ================================================================ */
#if 0

#include <stdio.h>

/* ---- 模拟串口场景 ---- */

#define UART_RX_BUF_SIZE  256    /* 必须是 2 的幂 */
static uint8_t   uart_rx_buffer[UART_RX_BUF_SIZE];
static ringbuf_t uart_rx_ring;

/* 初始化 */
void uart_init(void)
{
    ringbuf_init(&uart_rx_ring, uart_rx_buffer, UART_RX_BUF_SIZE);
}

/* 串口接收中断服务程序（生产者） */
void UART_RX_ISR(void)
{
    uint8_t byte = UART_DR;   /* 读取串口数据寄存器（平台相关） */
    ringbuf_put(&uart_rx_ring, byte);

    /* 也可批量写入（如从 DMA 缓冲区）： */
    // uint8_t dma_buf[64];
    // uint32_t cnt = ringbuf_puts(&uart_rx_ring, dma_buf, 64);
    // if (cnt < 64) { /* 缓冲区满，部分丢失 */ }
}

/* 主循环（消费者） */
void main_loop(void)
{
    uint8_t byte;

    while (1) {
        /* 逐个处理 */
        if (ringbuf_get(&uart_rx_ring, &byte)) {
            /* 处理 byte ... */
        }

        /* 或批量处理 */
        uint8_t buf[64];
        uint32_t cnt = ringbuf_gets(&uart_rx_ring, buf, sizeof(buf));
        for (uint32_t i = 0; i < cnt; i++) {
            /* 处理 buf[i] ... */
        }
    }
}

#endif
