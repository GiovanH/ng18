#!/bin/python3
"""Summary

Attributes:
    necessary_threads (int): Description
    necessary_threads : int
    Description
"""

from time import sleep
import threading
import progressbar
from pwidgets import DynamicProgressString
from snip import execif

necessary_threads = 1


def extraThreads():
    """
    Returns:
        int: Number of threads, not including main.
    """
    return threading.active_count() - necessary_threads


def threadWait(threshhold=0, interval=1, quiet=True, use_pbar=True):
    """Wait for threads to complete.
    
    Args:
        threshhold (int): Wait until at most X extra threads exist.
        interval (int, optional): Seconds between checking thread status
        quiet (bool, optional): Print detailed thread status
        use_pbar (bool, optional): Show progressbar
    
    Returns:
        TYPE: Description
    """
    if threshhold < 0:
        # Short circuit
        return

    pbar = None
    if use_pbar and (extraThreads() > threshhold):
        _max = extraThreads() - threshhold
        print("Finishing {} background jobs.".format(_max))
        pbar = progressbar.ProgressBar(max_value=_max, redirect_stdout=True)

    while (extraThreads() > threshhold):
        c = extraThreads() - threshhold

        if pbar:
            pbar.update(_max - c)

        if not quiet:
            print("Waiting for {} job{} to finish:".format(c, "s" if c > 1 else ""))
            print(threading.enumerate())

        sleep(interval)

    if pbar:
        pbar.finish()


def thread(target, *args, **kwargs):
    """Initialize and start a thread
    
    Args:
        target (function): Task to complete
        *args: Passthrough to threading.Thread
        **kwargs: threading.Thread
    """
    t = threading.Thread(target=target, *args, **kwargs)
    t.start()


class Spool():

    """A spool is a queue of threads.
    This is a simple way of making sure you aren't running too many threads at one time.
    At intervals, determined by `delay`, the spooler (if on) will start threads from the queue.
    The spooler can start multiple threads at once.
    """

    def __init__(self, quota, name=None, cfinish={}, belay=False):
        """Create a spool
        
        Args:
            quota (int): Size of quota, i.e. how many threads can run at once.
            cfinish (dict, optional): Description
        """
        super(Spool, self).__init__()
        self.quota = quota
        self.name = name
        self.cfinish = cfinish

        self.queue = []
        self.running_threads = []

        self.flushing = 0
        self._pbar_max = 0
        self.spoolThread = None
        self.background_spool = False
        self.dirty = threading.Event()

        if not belay:
            self.start()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.finish(resume=False, **self.cfinish)

    def __str__(self):
        return "{} at {}: {} threads queued, {}/{} currently running".format(type(self), hex(id(self)), len(self.queue), self.numRunningThreads, self.quota)

    # Interfaces

    def start(self):
        """Begin spooling threads in the background, if not already doing so. 
        """
        self.background_spool = True
        if not (self.spoolThread and self.spoolThread.is_alive()):
            self.spoolThread = threading.Thread(target=self.spoolLoop, name="Spooler")
            self.spoolThread.start()

    def finish(self, resume=False, verbose=False, use_pbar=True):
        """Block and complete all threads in queue.
        
        Args:
            resume (bool, optional): Resume spooling after finished
            verbose (bool, optional): Report progress towards queue completion.
            use_pbar (bool, optional): Graphically display progress towards queue completions
        """
        # Stop existing spools
        self.background_spool = False
        self.dirty.set()

        # By default, we don't use a callback.
        cb = None

        if verbose:
            print(self)

        # Progress bar management, optional.
        self._pbar_max = self.numRunningThreads + len(self.queue)
        if use_pbar and self._pbar_max > 0:
            widgets = [
                ("[{n}] ".format(n=self.name) if self.name else ''), progressbar.Percentage(),
                ' ', progressbar.SimpleProgress(format='%(value_s)s of %(max_value_s)s'),
                ' ', progressbar.Bar(),
                ' ', DynamicProgressString(name="state"),
                ' ', progressbar.Timer(),
                ' ', progressbar.AdaptiveETA(),
            ]
            self.progbar = progbar = progressbar.ProgressBar(max_value=self._pbar_max, widgets=widgets, redirect_stdout=True)

            def updateProgrssBar():
                # Update progress bar.
                q = (len(self.queue) if self.queue else 0)
                nrt = self.numRunningThreads
                progress = (self._pbar_max - (nrt + q))
                state = "[Spool: Q: {q:2}, R: {nrt:2}/{quota}]".format(quota=self.quota, **locals())
                progbar.max_value = self._pbar_max
                progbar.update(progress, state=state)
            cb = updateProgrssBar

        # assert not self.spoolThread.isAlive, "Background loop did not terminate"
        # Create a spoolloop, but block until it deploys all threads.
        execif(cb)
        while (self.queue and len(self.queue) > 0) or (self.numRunningThreads > 0):
            self.dirty.wait()
            self.doSpool(verbose=verbose)        
            self.dirty.clear()
            execif(cb)

        assert len(self.queue) == 0, "Finished without deploying all threads"
        assert self.numRunningThreads == 0, "Finished without finishing all threads"
        
        if cb:
            progbar.finish()

        if resume:
            self.queue.clear()  # Create a fresh queue
            self.start()

        if verbose:
            print(self)

    def flush(self):
        """Start and finishes all current threads before starting any new ones. 
        """
        self.flushing = 1

    def enqueue(self, target, args=tuple(), kwargs=dict(), *thargs, **thkwargs):
        """Add a thread to the back of the queue.
        
        Args:
            target (function): The function to execute
            name (str): Name of thread, for debugging purposes
            args (tuple, optional): Description
            kwargs (dict, optional): Description

            *thargs: Args for threading.Thread
            **thkwargs: Kwargs for threading.Thread
        """
        def runAndFlag():
            target(*args, **kwargs)
            self.dirty.set()
        self.queue.append(threading.Thread(target=runAndFlag, *thargs, **thkwargs))
        self._pbar_max += 1
        self.dirty.set()

    def setQuota(self, newQuota):
        self.quota = newQuota
        self.dirty.set()

    def enqueueSeries(self, targets):
        """Queue a series of tasks that are interdepenent. 
        Just a wrapper that creates a closure around functions, then queues them.
        
        Args:
            targets (list): A list of functions
        """
        def closure():
            for target in targets:
                target()
            self.dirty.set()
        self.queue.append(threading.Thread(target=closure))
        self.dirty.set()

    ##################
    # Minor utility
    ##################

    def startThread(self, newThread):
        self.running_threads.append(newThread)
        newThread.start()
        self.dirty.set()

    @property    
    def numRunningThreads(self):
        """Accurately count number of "our" running threads.
        This prunes dead threads and returns a count of live threads.
        
        Returns:
            int: Number of running threads owned by this spool
        """
        self.running_threads = [
            thread
            for thread in self.running_threads
            if thread.is_alive()
        ]
        return len(self.running_threads)

    ##################
    # Spooling
    ##################

    def spoolLoop(self, verbose=False):
        """Periodically start additional threads, if we have the resources to do so.
        This function is intended to be run as a thread.
        Runs until the queue is empty or, if self.background_spool is true, runs forever.
        
        Args:
            verbose (bool, optional): Report progress towards queue completion.
        """
        while self.background_spool:
            self.dirty.wait()
            #   self.dirty.set()
            self.doSpool(verbose=verbose)        
            self.dirty.clear()

    def doSpool(self, verbose=False):
        """Spools new threads until the queue empties or the quota fills.
        
        Args:
            verbose (bool, optional): Verbose output
        """

        if self.flushing == 1:
            # Finish running threads
            if self.numRunningThreads == 0:
                self.flushing = 0
            else:
                return
            # elif self.flushing == 2:
            #     # Deploy entire queue
            #     if len(self.queue) == 0:
            #         self.flushing = 3
            # elif self.flushing == 3:
            #     self.flushing = 0

            # else:
            #     # Otherwise don't deploy
            #     return

        # Start threads until we've hit quota, or until we're out of threads.
        while len(self.queue) > 0 and (self.numRunningThreads < self.quota):
            self.startThread(self.queue.pop(0))

        if verbose:
            print(self.running_threads)
            print("{} threads queued, {}/{} currently running.".format(len(self.queue), self.numRunningThreads, self.quota))


def test():
    """Test threading functionality
    """
    from time import sleep
    from random import random

    work = []

    def dillydally(i, wait):
        # print("Job", i, "started.")
        sleep(wait)
        work.append(i)
        # print("Job", i, "done.")

    # with Spool(8, cpbar=True) as s:
    # Spool = FastSpool

    def test_simple_finish():
        print("Test simple w/ finish.")

        work.clear()
        s = Spool(2)
        for i in range(0, 10):
            s.enqueue(target=dillydally, args=(i, 1))

        # sleep(4)
        print("Finish.")
        s.finish(use_pbar=True)
        print(work, len(work))
        assert len(work) == 10

        # work.clear()
        # s = Spool(2)
        # for i in range(0, 10):
        #     s.enqueue(target=dillydally, args=(i, 1))

        # sleep(4)
        # print("Quiet Finish.")
        # s.finish(use_pbar=False)
        # print(work, len(work))

        # work.clear()
        # s = Spool(2)
        # for i in range(0, 10):
        #     s.enqueue(target=dillydally, args=(i, 1))

        # sleep(4)
        # print("Finish and resume.")
        # s.finish(use_pbar=True, resume=True)
        # for i in range(10, 20):
        #     s.enqueue(target=dillydally, args=(i, 1))
        # sleep(12)
        # print("Finish.")
        # s.finish(use_pbar=True)
        # assert len(work) == 20

    def test_wrapper():
        print("Test wrapper.")

        work.clear()
        with Spool(2) as w:
            for i in range(0, 10):
                w.enqueue(target=dillydally, args=(i, 3 + random()))

            sleep(2)
            print("Finish.")
        print(work, len(work))
        assert len(work) == 10

        work.clear()
        with Spool(2) as w:
            for i in range(0, 10):
                w.enqueue(target=dillydally, args=(i, random()))

            sleep(2)
            print("Delayed Finish.")
        print(work, len(work))
        assert len(work) == 10

        work.clear()
        with Spool(2) as w:
            for i in range(0, 10):
                w.enqueue(target=dillydally, args=(i, random()))

            sleep(2)
            print("Quiet finish.")
        print(work, len(work))
        assert len(work) == 10


    def test_morework():
        work.clear()

        def nestedWork(sp):
            work.append("x")
            if sp:
                sp.enqueue(nestedWork, (None,))
                sp.enqueue(nestedWork, (None,))

        with Spool(4) as s:
            s.enqueue(nestedWork, (s,))
            s.enqueue(nestedWork, (s,))

        print(work, len(work))

        

    def test_midflush():
        print("Test mid-work flush.")
        work.clear()
        s = Spool(2)
        
        s.enqueue(target=dillydally, args=(1, 1))
        s.enqueue(target=dillydally, args=(2, 3))
        s.enqueue(target=dillydally, args=(3, 0))
        s.enqueue(target=dillydally, args=(4, 2))
        s.flush()
        s.enqueue(target=dillydally, args=(10, 1))
        s.enqueue(target=dillydally, args=(20, 3))
        s.enqueue(target=dillydally, args=(30, 0))
        s.enqueue(target=dillydally, args=(40, 2))

        sleep(5)
        print("Finish.")
        s.finish(use_pbar=True)
        print(work, len(work))
        assert len(work) == 8

    #    test_simple_finish()
    test_morework()
    # test_wrapper()
    # test_midflush()


if __name__ == '__main__':
    test()
