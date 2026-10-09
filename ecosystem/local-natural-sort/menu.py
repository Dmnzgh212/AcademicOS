"""Nondeveloper menu; all data access stays behind the independent Shell."""
from pathlib import Path
from types import SimpleNamespace
import subprocess

from sort_shell import run

HERE = Path(__file__).resolve().parent


def main():
    print('LifeHub 本地排序试用版（不读取文件，不联网）')
    print('仅支持英文/ASCII 名称：最多16行，每行64字符。')
    while True:
        print('\n1 导入模块  2 允许排序  3 排序  4 撤销权限  5 卸载  0 退出')
        try:
            choice = input('请选择：').strip()
            if choice == '0':
                return
            action = {'1': 'import', '2': 'enable', '3': 'sort',
                      '4': 'disable', '5': 'remove'}.get(choice)
            if action is None:
                print('请输入0到5。')
                continue
            labels = []
            if action == 'sort':
                print('每行输入一个名称；输入空行开始排序。')
                while True:
                    line = input()
                    if not line:
                        break
                    labels.append(line)
                    if len(labels) > 16:
                        raise RuntimeError('LHSORT_INPUT_LIMIT：最多16行。')
            run(SimpleNamespace(action=action, labels=labels, workspace=HERE / 'workspace',
                                packages=HERE / 'packages', yes=False))
        except (EOFError, KeyboardInterrupt):
            print('\n已退出；退出不会撤销已有权限，可重新打开后选择4。')
            return
        except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
            print(str(exc) if isinstance(exc, RuntimeError) else
                  f'LHSORT_ERROR {type(exc).__name__}')
            print('请复制以上LHSORT错误代码反馈；不要发送私有名称或整个工作目录。')


if __name__ == '__main__':
    main()
