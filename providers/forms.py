# providers/forms.py
from django import forms
from .models import Provedor, Contato, CidadeAtendida

class ProvedorForm(forms.ModelForm):
    class Meta:
        model = Provedor
        fields = [
            'nome', 'ativo', 'razao_social', 'cnpj', 
            'parceiro_bst', 'fibra', 'radio', 
            'link_dedicado', 'link_banda_larga', 'zona_rural'
        ]
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'razao_social': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'cnpj': forms.TextInput(attrs={'class': 'form-control bg-dark text-white border-secondary'}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            # Adicione os novos para o visual do card
            'fibra': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'radio': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'link_dedicado': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'link_banda_larga': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'zona_rural': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'parceiro_bst': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        
class ContatoForm(forms.ModelForm):
    class Meta:
        model = Contato
        fields = ['nome', 'cargo', 'telefone', 'email',] # Inclua aqui
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control bg-dark text-white'}),
            'cargo': forms.TextInput(attrs={'class': 'form-control bg-dark text-white'}),
            'telefone': forms.TextInput(attrs={'class': 'form-control bg-dark text-white'}),
            'email': forms.EmailInput(attrs={'class': 'form-control bg-dark text-white'}),
             # Adicione o widget
        }
        
class CidadeForm(forms.ModelForm):
    class Meta:
        model = CidadeAtendida
        fields = ['nome', 'uf']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control bg-dark text-white'}),
            'uf': forms.TextInput(attrs={'class': 'form-control bg-dark text-white'}),
        }