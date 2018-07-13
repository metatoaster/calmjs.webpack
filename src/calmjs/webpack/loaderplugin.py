# -*- coding: utf-8 -*-
"""
Loader plugin registry and handlers for webpack.

Currently a loader plugin registry for webpack is provided to allow the
mapping of named loader plugins to the intended locations.
"""

import shutil
import logging
from os import makedirs
from os.path import dirname
from os.path import exists
from os.path import join

from calmjs.toolchain import BUILD_DIR

from calmjs.loaderplugin import LoaderPluginRegistry
from calmjs.loaderplugin import LoaderPluginHandler
from calmjs.loaderplugin import NPMLoaderPluginHandler

logger = logging.getLogger(__name__)


class BaseWebpackLoaderHandler(LoaderPluginHandler):
    """
    The base webpack loader implementation that works well for data file
    argument that are supplied by the final loader, that will also
    require copying.

    Subclasses may override the run method for specific purposes.  One
    possible way is to supply the original source file as the target,
    if it is infeasible to be copied (due to size and/or the processing
    is meant to be done through the specific webpack loader).
    """

    def run(self, toolchain, spec, modname, source, target, modpath):
        stripped_modname = self.unwrap(modname)
        copy_target = join(spec[BUILD_DIR], target)
        if not exists(dirname(copy_target)):
            makedirs(dirname(copy_target))
        # TODO make use of spec/toolchain copy manifest/function,
        # if/when that is implemented for source/dest tracking?
        # this may be useful to reduce the amount of data moved around.
        shutil.copy(source, copy_target)

        modpaths = {modname: modpath}
        targets = {
            stripped_modname: target,
            # Also include the relative path as a default alias so that
            # within the context of the loader, any implicit joining of
            # the current directory (i.e. './') with any declared
            # modnames within the system will not affect the ability to
            # do bare imports (e.g. "namespace/package/resource.data")
            # within the loader's interal import system.
            #
            # Seriously, forcing the '~' prefixes on all user imports
            # is simply unsustainable importability.
            './' + stripped_modname: target,
        }
        return modpaths, targets, self.finalize_export_module_names(
            toolchain, spec, [modname])

    def chained_call(
            self, chained,
            toolchain, spec, stripped_modname, source, target, modpath):
        # In general, only the innermost item matters.
        inner_modpaths, targets, inner_export_module_names = (
            chained.__call__(
                toolchain, spec, stripped_modname, source, target, modpath)
        )
        # need to wrap the inner_modpaths with the plugin name for
        # the values that export as modname
        modpaths = {
            self.name + '!' + k: v
            for k, v in inner_modpaths.items()
        }
        return modpaths, targets, self.finalize_export_module_names(
                toolchain, spec, inner_export_module_names, self.name)

    def generate_export_module_names(
            self, toolchain, spec, export_module_names, prefix=''):
        if prefix:
            return [prefix + '!' + v for v in export_module_names]
        return list(export_module_names)

    def finalize_export_module_names(
            self, toolchain, spec, export_module_names, prefix=''):
        """
        The standard method for finalizing the export module names
        produced for modules that involve the module loader syntax.
        These are the names that will end up in the generated calmjs
        export module.
        """

        return self.generate_export_module_names(
            toolchain, spec, export_module_names, prefix)

    def __call__(self, toolchain, spec, modname, source, target, modpath):
        stripped_modname = self.unwrap(modname)
        chained = (
            self.registry.get_record(stripped_modname)
            if '!' in stripped_modname else None)
        if chained:
            return self.chained_call(
                chained,
                toolchain, spec, stripped_modname, source, target, modpath,
            )

        return self.run(toolchain, spec, modname, source, target, modpath)


class WebpackLoaderHandler(NPMLoaderPluginHandler, BaseWebpackLoaderHandler):
    """
    The default webpack loader handler class.

    Typically, webpack loaders are sourced from npm under packages that
    are called {name}-loader, where the name is the name of the loader.
    This greatly simplifies how the loaders can be constructed and
    resolved.
    """

    @property
    def node_module_pkg_name(self):
        return self.name + '-loader'


class AutogenWebpackLoaderHandler(WebpackLoaderHandler):
    """
    Special class for the default loader registry.
    """


class AutogenWebpackLoaderPluginRegistry(LoaderPluginRegistry):
    """
    A special registry that will construct/return a loader handler class
    for cases where they are not available.
    """

    def get_record(self, name):
        rec = super(AutogenWebpackLoaderPluginRegistry, self).get_record(name)
        if rec:
            return rec

        plugin_name = self.to_plugin_name(name)
        logger.debug(
            "%s registry '%s' generated loader handler '%s'",
            self.__class__.__name__, self.registry_name, plugin_name
        )
        return AutogenWebpackLoaderHandler(self, plugin_name)
