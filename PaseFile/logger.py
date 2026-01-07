"""统一的自定义日志记录器模块"""
import logging


def get_logger(name: str = __name__, level=logging.INFO) -> logging.Logger:
    """
    获取或创建日志记录器，确保每个日志记录器只添加一次处理器。


    Args:
        name: 日志记录器名称，通常使用 __name__
        level: 日志级别

    Returns:
        logging.Logger 实例
    """
    logger = logging.getLogger(name)

    if not logger.handlers:  
        logger.setLevel(level)

        ch = logging.StreamHandler()
        ch.setLevel(level)

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        ch.setFormatter(formatter)

        logger.addHandler(ch)

    return logger