from multiprocessing import freeze_support


def run():
    from zap.zap import run as run_zap
    run_zap()

if __name__ == "__main__":
    freeze_support()
    run()
