njord
=====
A package to generalize and simplify working with different types of 
geophysical/oceanographical/meterological data. The package allows for 
analysis and presentation of data from different sources in a unified
way and provides a number of functions for this. The package requires
some work to when first setup, both by editing the config file and 
most likely adding modules/classes. 

The structure is as follows: 

A class represents a specific dataset.
A module contains all classes from the same source. They are normally
setup in the same format. 


Installation
------------
 - (Edit config file and add modules/classes.)
 - sudo python setup.py install      # global installation
 - python setup.py install --user    # installation for current user

Define a project in one of the following files:

./njord.cfg
~/.njord.cfg
/path/to/package/njord.cfg

Example:

```ini
[Default]
basedir:     /projData

[rutgers.Coral]
datadir:     %(basedir)s/rutgers/CORAL/
gridfile:    %(datadir)s/coral_grd.nc
map_region:  indthr
imt:         1281
jmt:         641
```

Usage
-----
```python
>>> from njord import rutgers 
>>>
>>> #Create a grid instance
>>> mp = rutgers.Coral('handle')
>>>
>>> #Load u-velociites
>>> mp.load('u')
```