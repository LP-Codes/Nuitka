#     Copyright 2012, Kay Hayen, mailto:kay.hayen@gmail.com
#
#     Part of "Nuitka", an optimizing Python compiler that is compatible and
#     integrates with CPython, but also works on its own.
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
#
""" Node the calls to the 'range' builtin.

This is a rather complex beast as it has many cases, is difficult to know if it's sizable
enough to compute, and there are complex cases, where the bad result of it can be
predicted still, and these are interesting for warnings.

"""

from .NodeBases import (
    CPythonExpressionChildrenHavingBase,
    CPythonSideEffectsFromChildrenMixin,
    CPythonExpressionBuiltinNoArgBase
)

from .NodeMakingHelpers import (
    makeConstantReplacementNode,
    getComputationResult
)

from nuitka.transform.optimizations import BuiltinOptimization

from nuitka.Utils import python_version

import math

class CPythonExpressionBuiltinRange0( CPythonExpressionBuiltinNoArgBase ):
    kind = "EXPRESSION_BUILTIN_RANGE0"

    def __init__( self, source_ref ):
        CPythonExpressionBuiltinNoArgBase.__init__(
            self,
            builtin_function = range,
            source_ref       = source_ref
        )

    def mayHaveSideEffects( self, constraint_collection ):
        return False


class CPythonExpressionBuiltinRangeBase( CPythonExpressionChildrenHavingBase ):

    def __init__( self, values, source_ref ):
        CPythonExpressionChildrenHavingBase.__init__(
            self,
            values     = values,
            source_ref = source_ref
        )

    def getTruthValue( self, constraint_collection ):
        length = self.getIterationLength( constraint_collection )

        if length is None:
            return None
        else:
            return length > 0

    def mayHaveSideEffects( self, constraint_collection ):
        for child in self.getVisitableNodes():
            if child.mayHaveSideEffects( constraint_collection ):
                return True

            if child.getIntegerValue( constraint_collection ) is None:
                return True

        else:
            return False


class CPythonExpressionBuiltinRange1( CPythonExpressionBuiltinRangeBase ):
    kind = "EXPRESSION_BUILTIN_RANGE1"

    named_children = ( "low", )

    def __init__( self, low, source_ref ):
        assert low is not None

        CPythonExpressionBuiltinRangeBase.__init__(
            self,
            values     = {
                "low"  : low,
            },
            source_ref = source_ref
        )

    getLow = CPythonExpressionChildrenHavingBase.childGetter( "low" )

    def computeNode( self, constraint_collection ):
        # TODO: Support Python3 range objects too.
        if python_version >= 300:
            return self, None, None

        given_values = ( self.getLow(), )

        if not BuiltinOptimization.builtin_range_spec.isCompileTimeComputable( given_values ):
            return self, None, None

        return getComputationResult(
            node        = self,
            computation = lambda : BuiltinOptimization.builtin_range_spec.simulateCall( given_values ),
            description = "Builtin call to range precomputed."
        )

    def getIterationLength( self, constraint_collection ):
        low = self.getLow().getIntegerValue( constraint_collection )

        if low is None:
            return None

        return max( 0, low )

    def canPredictIterationValues( self, constraint_collection ):
        return self.getIterationLength( constraint_collection ) is not None

    def getIterationValue( self, element_index, constraint_collection ):
        length = self.getIterationLength( constraint_collection )

        if length is None:
            return None

        if element_index > length:
            return None

        # TODO: Make sure to cast element_index to what CPython will give, for now a
        # downcast will do.
        return makeConstantReplacementNode(
            constant = int( element_index ),
            node     = self
        )

    def isKnownToBeIterable( self, count ):
        return count is None or count == self.getIterationLength()


class CPythonExpressionBuiltinRange2( CPythonExpressionBuiltinRangeBase ):
    kind = "EXPRESSION_BUILTIN_RANGE2"

    named_children = ( "low", "high" )

    def __init__( self, low, high, source_ref ):
        CPythonExpressionBuiltinRangeBase.__init__(
            self,
            values     = {
                "low"  : low,
                "high" : high
            },
            source_ref = source_ref
        )

    getLow  = CPythonExpressionChildrenHavingBase.childGetter( "low" )
    getHigh = CPythonExpressionChildrenHavingBase.childGetter( "high" )

    builtin_spec = BuiltinOptimization.builtin_range_spec

    def computeBuiltinSpec( self, given_values ):
        assert self.builtin_spec is not None, self

        if not self.builtin_spec.isCompileTimeComputable( given_values ):
            return self, None, None

        return getComputationResult(
            node        = self,
            computation = lambda : self.builtin_spec.simulateCall( given_values ),
            description = "Builtin call to %s precomputed." % self.builtin_spec.getName()
        )

    def computeNode( self, constraint_collection ):
        if python_version >= 300:
            return self, None, None

        low  = self.getLow()
        high = self.getHigh()

        return self.computeBuiltinSpec( ( low, high ) )

    def getIterationLength( self, constraint_collection ):
        low  = self.getLow()
        high = self.getHigh()

        low = low.getIntegerValue( constraint_collection )

        if low is None:
            return None

        high = high.getIntegerValue( constraint_collection )

        if high is None:
            return None

        return max( 0, high - low )

    def canPredictIterationValues( self, constraint_collection ):
        return self.getIterationLength( constraint_collection ) is not None

    def getIterationValue( self, element_index, constraint_collection ):
        low  = self.getLow()
        high = self.getHigh()

        low = low.getIntegerValue( constraint_collection )

        if low is None:
            return None

        high = high.getIntegerValue( constraint_collection )

        if high is None:
            return None

        result = low + element_index

        if result >= high:
            return None
        else:
            return makeConstantReplacementNode(
                constant = result,
                node     = self
            )

    def isKnownToBeIterable( self, count ):
        return count is None or count == self.getIterationLength()


class CPythonExpressionBuiltinRange3( CPythonExpressionBuiltinRangeBase ):
    kind = "EXPRESSION_BUILTIN_RANGE3"

    named_children = ( "low", "high", "step" )

    def __init__( self, low, high, step, source_ref ):
        CPythonExpressionBuiltinRangeBase.__init__(
            self,
            values     = {
                "low"  : low,
                "high" : high,
                "step" : step
            },
            source_ref = source_ref
        )

    getLow  = CPythonExpressionChildrenHavingBase.childGetter( "low" )
    getHigh = CPythonExpressionChildrenHavingBase.childGetter( "high" )
    getStep = CPythonExpressionChildrenHavingBase.childGetter( "step" )

    builtin_spec = BuiltinOptimization.builtin_range_spec

    def computeBuiltinSpec( self, given_values ):
        assert self.builtin_spec is not None, self

        if not self.builtin_spec.isCompileTimeComputable( given_values ):
            return self, None, None

        return getComputationResult(
            node        = self,
            computation = lambda : self.builtin_spec.simulateCall( given_values ),
            description = "Builtin call to %s precomputed." % self.builtin_spec.getName()
        )

    def computeNode( self, constraint_collection ):
        if python_version >= 300:
            return self, None, None

        low  = self.getLow()
        high = self.getHigh()
        step = self.getStep()

        return self.computeBuiltinSpec( ( low, high, step ) )

    def getIterationLength( self, constraint_collection ):
        low  = self.getLow()
        high = self.getHigh()
        step = self.getStep()

        low = low.getIntegerValue( constraint_collection )

        if low is None:
            return None

        high = high.getIntegerValue( constraint_collection )

        if high is None:
            return None

        step = step.getIntegerValue( constraint_collection )

        if step is None:
            return None

        # Give up on this, will raise ValueError.
        if step == 0:
            return None

        if low < high:
            if step < 0:
                estimate = 0
            else:
                estimate = math.ceil( float( high - low ) / step )
        else:
            if step > 0:
                estimate = 0
            else:
                estimate = math.ceil( float( high - low ) / step )

        estimate = round( estimate )

        assert not estimate < 0

        return int( estimate )

    def canPredictIterationValues( self, constraint_collection ):
        return self.getIterationLength( constraint_collection ) is not None

    def getIterationValue( self, element_index, constraint_collection ):
        low  = self.getLow().getIntegerValue( constraint_collection )

        if low is None:
            return None

        high = self.getHigh().getIntegerValue( constraint_collection )

        if high is None:
            return None

        step = self.getStep().getIntegerValue( constraint_collection )

        result = low + step * element_index

        if result >= high:
            return None
        else:
            return makeConstantReplacementNode(
                constant = result,
                node     = self
            )

    def isKnownToBeIterable( self, count ):
        return count is None or count == self.getIterationLength()
