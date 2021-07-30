# Fabric script for hubmoni installation.  
# See the INSTALL file for usage.
#
import sys
import time
import os.path
from fabric2 import Connection, task, ThreadingGroup
from invoke import run as local

import hubmonitools

HUBMONICMD = "hubmoni"
CRONCMD = "source \$HOME/env/bin/activate && "+HUBMONICMD

# Remote hosts list: all of the hubs on this cluster
hubconf = hubmonitools.HubConfig(hubConfigFile="resources/hubConfig.json")
(host, cluster) = hubmonitools.getHostCluster()
hubhosts = hubconf.hubs(cluster)

def installCronjob(c, label, job):
    bashstr = '(crontab -l 2>/dev/null | grep -x \"# %s" > /dev/null 2>/dev/null)' % label
    bashstr += ' || (crontab -l 2>/dev/null | { cat; echo \"# %s\";' % label
    bashstr += 'echo \"%s\"; } | crontab -)' % job
    c.run(bashstr)

def removeCronjob(c, label):
    bashstr = 'crontab -l 2>/dev/null | sed \'/# %s/,+1d\' | crontab -' % label
    c.run(bashstr)
    
@task
def deploy(ctx):
    # Stop everything
    stop(ctx)

    # Install the configuration files
    config(ctx)

    # create a new source distribution as tarball
    local('python setup.py sdist --formats=gztar')

    # figure out the release name and version
    output = local('python setup.py --fullname')
    dist = output.stdout.strip()

    if not hasattr(ctx, 'host'):
        group = ThreadingGroup(*hubhosts)
    else:
        group = ThreadingGroup(ctx.host)

    for c in group:
        # upload the source tarball to the temporary folder on the server
        c.put('dist/%s.tar.gz' % dist, '/tmp/%s.tar.gz' % dist)
        # now install the package with pip
        c.run('pip install --upgrade /tmp/%s.tar.gz' % dist)
        # delete the tarball
        c.run('rm -f /tmp/%s.tar.gz' % dist)

        # Remove any old cron jobs
        removeCronjob(c, "hubmoni cron")
        removeCronjob(c, "hubmoni-reboot cron")
        # Install the cron jobs
        installCronjob(c, "hubmoni cron", "*/10 * * * * %s" % CRONCMD)
        installCronjob(c, "hubmoni-reboot cron", "@reboot %s" % CRONCMD)

@task
def config(ctx):
    if not hasattr(ctx, 'host'):
        group = ThreadingGroup(*hubhosts)
    else:
        group = ThreadingGroup(ctx.host)

    # Install the configuration files
    for c in group:
        c.put('resources/hubConfig.json', 'hubConfig.json')
        if os.path.isfile('resources/hubmoni.%s.config' % cluster):
            c.put('resources/hubmoni.%s.config' % cluster, 'hubmoni.config')
        else:
            c.put('resources/hubmoni.config', 'hubmoni.config')

@task
def stop(ctx):
    if not hasattr(ctx, 'host'):
        group = ThreadingGroup(*hubhosts)
    else:
        group = ThreadingGroup(ctx.host)

    for c in group:
        c.run('ps aux | grep %s | grep -v grep | awk \'{print $2}\' | xargs -r kill -TERM' 
            % os.path.basename(HUBMONICMD))

@task
def restart(ctx):
    stop(ctx)
    # Cron will restart for us!

# the user to use for the remote commands
# env.user = CRON_USER
