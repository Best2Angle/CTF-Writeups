from fractions import gcd
from Crypto.PublicKey import RSA
import requests
import re
import signal
import wienerAttack
import datetime
#Note this file is Linux only because of usage of signal.

#TODO Add Sieve improvement to Fermat Attack
#https://en.wikipedia.org/wiki/Fermat's_factorization_method
class Factorizer:
    """
    RSA Factorization Utility written by Valar_Dragon for use in CTF's.
    It is meant for factorizing large modulii
    Currently it checks Factor DB, performs the Wiener Attack, fermat attack, and GCD between multiple keys.
    """
    def __init__(self):
        #Eventually put logging here@
        #this is the number to be added to x^2 in pollards rho.
        self.pollardRhoConstant1 = 1
        #this is the number to be multiplied to x^2 in pollards rho.
        self.pollardRhoConstant2 = 1
        self.keyNotFound = "key not found"

    def factorModulus(self,pubKey,outFileName=""):
        self.e = pubKey.e
        self.modulus = pubKey.n
        self.outFileName = outFileName
        self.p = -1
        self.q = -1

        print("[*] Checking Factor DB...")
        self.checkFactorDB()
        if(self.p != -1 and self.q != -1):
            print("[*] Factors are: %s and %s" % (self.p,self.q))
            return self.generatePrivKey()
        print("[x] Factor DB did not have the modulus")

        print("[*] Trying Wiener Attack...")
        if(len(str(self.e))*3 > len(str(self.modulus))):
            print("[*] Wiener Attack is likely to be succesful, increasing its timeout to 8 minutes")
            self.wienerAttack(wienerTimeout=8*60)
        else:
            self.wienerAttack()
        if(self.p != -1 and self.q != -1):
            print("[*] Wiener Attack Successful!!")
            print("[*] Factors are: %s and %s" % (self.p,self.q))
            return self.generatePrivKey()
        print("[x] Wiener Attack Failed")

        print("[*] Trying Fermat Attack...")
        self.fermatAttack()
        if(self.p != -1 and self.q != -1):
            print("[*] Fermat Attack Successful!!")
            print("[*] Factors are: %s and %s" % (self.p,self.q))
            return self.generatePrivKey()

        print("[*] Trying Pollards P-1 Attack...")
        self.pollardPminus1()
        if(self.p != -1 and self.q != -1):
            print("[*] Pollards P-1 Factorization Successful!!")
            print("[*] Factors are: %s and %s" % (self.p,self.q))
            return self.generatePrivKey()

        return self.keyNotFound

    def factorModulii(self,pubkeys,outFileNameFormat="privkey-%s.pem"):
        success = [-1]*len(pubkeys)
        privkeys = []
        print("[*] Trying multi-key attacks")
        print("[*] Searching for common factors (GCD Attack)")
        for i in range(len(pubkeys)):
            for j in range(i):
                if(success[i]==True and True==success[j]):
                    continue
                greatestCommonDivisor = gcd(pubkeys[i].n,pubkeys[j].n)
                if(greatestCommonDivisor != 1):
                    print("[*] Common Factor Found between key-%s and key-%s!!!"
                        % (i,j))
                    print("[*] Generating respective privatekeys")
                    for k in [i,j]:
                        success[k]=True
                        privkeys.append(self.generatePrivKey(modulus=pubkeys[k].n,
                            pubexp=pubkeys[k].e,p=greatestCommonDivisor,
                            q=pubkeys[k].n//greatestCommonDivisor,
                            outFileName=outFileNameFormat%k))
        for i in range(len(pubkeys)):
            if(success[i]==True):
                print("Key #%s already factored!"%i)
                continue
            print("Factoring key #%s"%i)
            privkey = self.factorModulus(pubkeys[i],outFileName=outFileNameFormat%i)
            if(privkey == self.keyNotFound):
                success[i]==False
            else:
                privkeys.append(privkey)
                success[i]==True





    #----------------BEGIN FACTOR DB SECTION------------------#

    def checkFactorDB(self, modulus="modulus"):
        """See if the modulus is already factored on factordb.com,
         and if so get the factors"""
        if(modulus=="modulus"): modulus = self.modulus
        # Factordb gives id's of numbers, which act as links for full number
        # follow the id's and get the actual numbers
        r = requests.get('http://www.factordb.com/index.php?query=%i' % self.modulus)
        regex = re.compile("index\.php\?id\=([0-9]+)", re.IGNORECASE)
        ids = regex.findall(r.text)
        # These give you ID's to the actual number
        p_id = ids[1]
        q_id = ids[2]
        # follow ID's
        regex = re.compile("value=\"([0-9]+)\"", re.IGNORECASE)
        r_1 = requests.get('http://www.factordb.com/index.php?id=%s' % p_id)
        r_2 = requests.get('http://www.factordb.com/index.php?id=%s' % q_id)
        # Get numbers
        self.p = int(regex.findall(r_1.text)[0])
        self.q = int(regex.findall(r_2.text)[0])
        if(self.p == self.q == self.modulus):
            self.p = -1
            self.q = -1



    #------------------END FACTOR DB SECTION------------------#
    #---------------BEGIN WIENER ATTACK SECTION---------------#
    #This comes from  https://github.com/sourcekris/RsaCtfTool/blob/master/wiener_attack.py
    def wienerAttack(self,modulus="modulus",pubexp="e",wienerTimeout=3*60):
        if(modulus=="modulus"): modulus = self.modulus
        if(pubexp=="e"): pubexp = self.e
        try:
            with timeout(seconds=wienerTimeout):
                wiener = wienerAttack.WienerAttack(self.modulus, self.e)
                if wiener.p is not None and wiener.q is not None:
                    self.p = wiener.p
                    self.q = wiener.q
        except TimeoutError:
            print("[x] Wiener Attack went over %s seconds "% wienerTimeout)


    #----------------END WIENER ATTACK SECTION----------------#
    #-----------BEGIN Fermat Factorization SECTION------------#

    def isLastDigitPossibleSquare(self,x):
        if(x < 0):
            return False
        lastDig = x & 0xF
        if(lastDig > 9):
            return False
        if(lastDig < 2):
            return True
        if(lastDig == 4 or lastDig == 5 or lastDig == 9):
            return True
        return False

    #TODO Implement Sieve improvement!
    #(https://en.wikipedia.org/wiki/Fermat's_factorization_method#Sieve_improvement)
    #Fermat factorization method written by me, inspired from wikipedia :D
    def fermatAttack(self,N="modulus",limit=100,fermatTimeout=3*60):
        if(N=="modulus"): N = self.modulus
        try:
            with timeout(seconds=fermatTimeout):
                a = self.floorSqrt(N)+1
                b2 = a*a - N
                for i in range(limit):
                    if(self.isLastDigitPossibleSquare(b2)):
                        b = self.floorSqrt(b2)
                        if(b**2 == a*a-N):
                            #We found the factors!
                            self.p = a+b
                            self.q = a-b
                            return
                    a = a+1
                    b2 = a*a-N
                if(i==limit-1):
                    print("[x] Fermat Iteration Limit Exceeded")
        except TimeoutError:
            print("[x] Fermat Timeout Exceeded")




    #------------END Fermat Factorization SECTION-------------#
    #----------------BEGIN POLLARDS P-1 SECTION---------------#

    #Pollard P minus 1 factoring, using the algorithm as described by
    # https://math.berkeley.edu/~sagrawal/su14_math55/notes_pollard.pdf
    # Then I further modified it by using the standard "B" as the limit, and only
    # taking a to the power of a prime. Then from looking at wikipedia and such,
    # I took the gcd out of the loop, and put it at the end.
    # TODO Update this to official wikipedia definition, once I find an explanation of
    # Wikipedia definition. (I.e. Why it works)
    def pollardPminus1(self,N="modulus",a=7,B=2**16,pMinus1Timeout=3*60):
        if(N=="modulus"): N = self.modulus
        from sympy import sieve
        try:
            with timeout(seconds=pMinus1Timeout):
                brokeEarly = False
                for x in sieve.primerange(1, B):
                    tmp = 1
                    while tmp < B:
                        a = pow(a, x, N)
                        tmp *= x
                d = gcd(a-1,N)
                if(d==N):
                    #try next a value
                    print('[x] Unlucky choice of a, try restarting Pollards P-1 with a different a')
                    brokeEarly = True
                    return
                elif(d>1):
                    #Success!
                    self.p = d
                    self.q = N//d
                    return
                if(brokeEarly == False):
                    print("[x] Pollards P-1 did not find the factors with B=%s"% B)
        except TimeoutError:
            print("[x] Pollard P-1 Timeout Exceeded")


    #-----------------END POLLADS P-1 SECTION-----------------#
    #---------------BEGIN POLLARDS RHO SECTION----------------#
    def f(self,x):
        return (self.pollardRhoConstant2*x*x + self.pollardRhoConstant1) % self.n

    def pollardsRho(self,n="modulus",rhoTimeout=5*60):
        if(n=="modulus"): n = self.modulus
        """
        Pollard's Rho method for factoring numbers.
        Explanation I based this off of:
        https://www.csh.rit.edu/~pat/math/quickies/rho/#algorithm
        This is apparently not the standard definition, and doesn't work well.
        """
        self.n = n
        xValues = [1]
        i = 2

        with timeout(seconds=rhoTimeout):
            while(True):
                if(i % 2 == 0):
                    #if(i%100000==0):
                        #print("on iteration %s " % i )
                    #Calculate GCD(n, x_k - x_(k/2)), to conserve memory I'm popping x_k/2
                    x_k = self.f(i)
                    xValues.append(x_k)
                    x_k2 = xValues.pop(0)
                    #if x_k2 >= x_k, their difference is negative and thus we can't do the GCD
                    if(x_k2 < x_k):
                        commonDivisor = gcd(n,x_k - x_k2)
                        if(commonDivisor > 1):
                            print("[*] Pollards Rho completed in %s iterations!" % i)
                            #print("Factors: " + str(commonDivisor) + ", " + str(n / commonDivisor))
                            assert commonDivisor * (n // commonDivisor) == n

                            return (commonDivisor, n // commonDivisor)
                else:
                    #Just append new x value
                    xValues.append(self.f(i))
                i+=1

    #-----------------END POLLADS RHO SECTION-----------------#
    #---------------BEGIN SHARED ALGORITHM SECTION----------------#


    def floorSqrt(self,n):
        x = n
        y = (x + 1) // 2
        while y < x:
            x = y
            y = (x + n // x) // 2
        return x

    def extended_gcd(self,aa, bb):
        """Extended Euclidean Algorithm,
        from https://rosettacode.org/wiki/Modular_inverse#Python
        """
        lastremainder, remainder = abs(aa), abs(bb)
        x, lastx, y, lasty = 0, 1, 1, 0
        while remainder:
            lastremainder, (quotient, remainder) = remainder, divmod(lastremainder, remainder)
            x, lastx = lastx - quotient*x, x
            y, lasty = lasty - quotient*y, y
        return lastremainder, lastx * (-1 if aa < 0 else 1), lasty * (-1 if bb < 0 else 1)

    def modinv(self,a, m):
        """Modular Multiplicative Inverse,
        from https://rosettacode.org/wiki/Modular_inverse#Python
        """
        g, x, y = self.extended_gcd(a, m)
        if g != 1:
            raise ValueError
        return x % m

    def generatePrivKey(self, modulus="modulus",pubexp="e",p="p",q="q",outFileName=""):
        if(modulus=="modulus"): modulus = self.modulus
        if(p=="p"): p = self.p
        if(pubexp=="e"): pubexp = self.e
        if(q=="q"): q = self.q
        if(outFileName==""): outFileName = self.outFileName
        if(outFileName==""): outFileName = "RSA_PrivKey_%s" % str(datetime.datetime.now())
        totn = (p-1)*(q-1)
        privexp = self.modinv(pubexp,totn)
        assert p*q == modulus
        #For some reason, Wieners attack returns "Integers" that throw type errors for not being "ints"
        #I don't get it, but casting fixes it.
        privKey = RSA.construct((modulus,pubexp,int(privexp),int(p),int(q)))
        #Write to File
        open(outFileName,'bw+').write(privKey.exportKey())
        print("Wrote private key to file %s " % outFileName)
    #----------------END SHARED ALGORITHM SECTION -----------------#

class timeout:
    def __init__(self, seconds=1, error_message='[*] Timeout'):
        self.seconds = seconds
        self.error_message = error_message
    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message)
    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)
    def __exit__(self, type, value, traceback):
        signal.alarm(0)
